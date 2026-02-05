"""
Email monitoring service for NF attachments.

Supports:
- XML files (direct NF-e/CT-e/NFS-e)
- PDF files (DANFE with embedded XML or text extraction)
- ZIP files (containing XMLs or PDFs)
"""

import os
import re
import tempfile
import zipfile
from io import BytesIO

import frappe
from frappe import _


def check_emails():
    """
    Scheduled job to check emails for NF attachments.

    Uses Frappe's Email Account to monitor incoming emails
    and process XML/PDF attachments.
    """
    settings = frappe.get_single("Nota Fiscal Settings")

    if not settings.enabled or not settings.email_import_enabled:
        return

    if not settings.email_account:
        return

    # Get unprocessed communications from the configured email account
    communications = frappe.get_all(
        "Communication",
        filters={
            "email_account": settings.email_account,
            "communication_type": "Communication",
            "sent_or_received": "Received",
            "nf_processed": 0
        },
        fields=["name", "subject", "content"],
        order_by="creation desc",
        limit=50
    )

    for comm in communications:
        try:
            process_email(comm["name"], settings)
        except Exception as e:
            frappe.log_error(str(e), f"Error processing email: {comm['name']}")


def check_nf_attachment(doc, method=None):
    """
    Hook called when a new Communication is created.

    Checks if the email contains NF attachments.
    """
    settings = frappe.get_single("Nota Fiscal Settings")

    if not settings.enabled or not settings.email_import_enabled:
        return

    if doc.communication_type != "Communication":
        return

    if doc.sent_or_received != "Received":
        return

    # Check if from configured email account
    if settings.email_account and doc.email_account != settings.email_account:
        return

    # Check subject patterns
    if settings.email_subject_patterns:
        patterns = settings.email_subject_patterns.split("\n")
        subject_matches = False

        for pattern in patterns:
            pattern = pattern.strip()
            if not pattern:
                continue

            if "*" in pattern:
                # Simple wildcard matching
                import fnmatch
                if fnmatch.fnmatch(doc.subject.lower(), pattern.lower()):
                    subject_matches = True
                    break
            elif pattern.lower() in doc.subject.lower():
                subject_matches = True
                break

        if not subject_matches:
            # Mark as processed (no match)
            frappe.db.set_value("Communication", doc.name, "nf_processed", 1)
            return

    # Queue processing
    frappe.enqueue(
        "brazil_nf.services.email_monitor.process_email",
        comm_name=doc.name,
        settings=None,  # Will reload
        queue="short"
    )


def process_email(comm_name, settings=None):
    """
    Process an email for NF attachments.

    Args:
        comm_name: Communication document name
        settings: Nota Fiscal Settings (optional)
    """
    if not settings:
        settings = frappe.get_single("Nota Fiscal Settings")

    comm = frappe.get_doc("Communication", comm_name)

    # Get attachments
    attachments = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Communication",
            "attached_to_name": comm_name
        },
        fields=["name", "file_name", "file_url"]
    )

    nf_found = 0
    errors = []

    for attachment in attachments:
        file_name = attachment["file_name"].lower()

        try:
            # Process based on file type
            if file_name.endswith(".xml"):
                if process_xml_attachment(attachment, comm, settings):
                    nf_found += 1

            elif file_name.endswith(".pdf"):
                result = process_pdf_attachment(attachment, comm, settings)
                nf_found += result

            elif file_name.endswith(".zip"):
                result = process_zip_attachment(attachment, comm, settings)
                nf_found += result

        except Exception as e:
            error_msg = f"Error processing {attachment['file_name']}: {str(e)}"
            errors.append(error_msg)
            frappe.log_error(error_msg, f"Email NF Processing Error: {comm_name}")

    # Mark as processed
    frappe.db.set_value("Communication", comm_name, "nf_processed", 1)

    if nf_found > 0:
        frappe.logger().info(f"Processed {nf_found} NF(s) from email: {comm_name}")

    if errors:
        frappe.logger().warning(f"Errors processing email {comm_name}: {errors}")


def process_xml_attachment(attachment, comm, settings):
    """
    Process a single XML attachment.

    Args:
        attachment: File document data
        comm: Communication document
        settings: Nota Fiscal Settings

    Returns:
        bool: True if NF was created/updated
    """
    from brazil_nf.services.xml_parser import NFXMLParser

    # Read file content
    file_content = get_file_content(attachment)
    if not file_content:
        return False

    # Try to decode as text
    try:
        if isinstance(file_content, bytes):
            xml_content = file_content.decode("utf-8")
        else:
            xml_content = file_content
    except UnicodeDecodeError:
        try:
            xml_content = file_content.decode("latin-1")
        except:
            return False

    return create_nf_from_xml(xml_content, comm, settings)


def process_pdf_attachment(attachment, comm, settings):
    """
    Process a PDF attachment.

    Tries to:
    1. Extract embedded XML from PDF (Brazilian NF)
    2. Extract text and parse NF data - chave de acesso (Brazilian NF)
    3. Parse as international invoice if not Brazilian

    Args:
        attachment: File document data
        comm: Communication document
        settings: Nota Fiscal Settings

    Returns:
        int: Number of NFs created/updated
    """
    file_content = get_file_content(attachment)
    if not file_content:
        return 0

    nf_count = 0

    # Try to extract embedded XML first (Brazilian NF)
    xml_contents = extract_xml_from_pdf(file_content)
    if xml_contents:
        for xml_content in xml_contents:
            if create_nf_from_xml(xml_content, comm, settings):
                nf_count += 1

    # If no embedded XML, try to extract data from PDF text
    if nf_count == 0:
        pdf_data = extract_data_from_pdf(file_content)
        if pdf_data and pdf_data.get("chave_de_acesso"):
            # Brazilian NF from PDF text
            if create_nf_from_pdf_data(pdf_data, file_content, attachment, comm, settings):
                nf_count += 1

    # If still no match, try to parse as international invoice
    if nf_count == 0:
        invoice_data = extract_international_invoice(file_content)
        if invoice_data:
            if create_nf_from_invoice_data(invoice_data, file_content, attachment, comm, settings):
                nf_count += 1

    return nf_count


def process_zip_attachment(attachment, comm, settings):
    """
    Process a ZIP attachment containing XMLs or PDFs.

    Args:
        attachment: File document data
        comm: Communication document
        settings: Nota Fiscal Settings

    Returns:
        int: Number of NFs created/updated
    """
    file_content = get_file_content(attachment)
    if not file_content:
        return 0

    nf_count = 0

    try:
        with zipfile.ZipFile(BytesIO(file_content), 'r') as zip_file:
            for name in zip_file.namelist():
                name_lower = name.lower()

                # Skip directories and hidden files
                if name.endswith('/') or name.startswith('__'):
                    continue

                try:
                    inner_content = zip_file.read(name)

                    if name_lower.endswith('.xml'):
                        try:
                            xml_content = inner_content.decode('utf-8')
                        except UnicodeDecodeError:
                            xml_content = inner_content.decode('latin-1')

                        if create_nf_from_xml(xml_content, comm, settings):
                            nf_count += 1

                    elif name_lower.endswith('.pdf'):
                        # Process PDF from within ZIP
                        xml_contents = extract_xml_from_pdf(inner_content)
                        for xml_content in xml_contents:
                            if create_nf_from_xml(xml_content, comm, settings):
                                nf_count += 1

                except Exception as e:
                    frappe.log_error(f"Error processing {name} from ZIP: {str(e)}")

    except zipfile.BadZipFile:
        frappe.log_error(f"Invalid ZIP file: {attachment['file_name']}")

    return nf_count


def get_file_content(attachment):
    """
    Get file content from attachment.

    Args:
        attachment: File document data

    Returns:
        bytes: File content or None
    """
    try:
        file_url = attachment.get("file_url", "")

        if file_url.startswith("/private/") or file_url.startswith("/files/"):
            file_path = frappe.get_site_path(file_url.lstrip("/"))
        else:
            file_path = frappe.get_site_path("public", file_url.lstrip("/"))

        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return f.read()

    except Exception as e:
        frappe.log_error(f"Error reading file {attachment.get('file_name')}: {str(e)}")

    return None


def extract_xml_from_pdf(pdf_content):
    """
    Extract embedded XML attachments from a PDF.

    Many DANFE PDFs have the NF-e XML embedded as an attachment.

    Args:
        pdf_content: PDF file content as bytes

    Returns:
        list: List of XML strings found
    """
    xml_contents = []

    try:
        # Try using pypdf (newer) or PyPDF2
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                frappe.logger().warning("pypdf/PyPDF2 not installed. Cannot extract XML from PDF.")
                return xml_contents

        reader = PdfReader(BytesIO(pdf_content))

        # Check for embedded files
        if "/Names" in reader.trailer.get("/Root", {}):
            root = reader.trailer["/Root"]
            if "/Names" in root:
                names = root["/Names"]
                if "/EmbeddedFiles" in names:
                    embedded = names["/EmbeddedFiles"]
                    if "/Names" in embedded:
                        file_names = embedded["/Names"]
                        # Process pairs (name, reference)
                        for i in range(0, len(file_names), 2):
                            if i + 1 < len(file_names):
                                name = file_names[i]
                                if isinstance(name, str) and name.lower().endswith('.xml'):
                                    try:
                                        file_spec = file_names[i + 1]
                                        if "/EF" in file_spec:
                                            ef = file_spec["/EF"]
                                            if "/F" in ef:
                                                stream = ef["/F"]
                                                data = stream.get_data()
                                                xml_contents.append(data.decode('utf-8'))
                                    except Exception:
                                        pass

        # Alternative: Check catalog for embedded files
        if hasattr(reader, 'attachments') and reader.attachments:
            for name, data in reader.attachments.items():
                if name.lower().endswith('.xml'):
                    try:
                        xml_contents.append(data.decode('utf-8'))
                    except:
                        pass

    except Exception as e:
        frappe.logger().debug(f"Error extracting XML from PDF: {str(e)}")

    return xml_contents


def extract_data_from_pdf(pdf_content):
    """
    Extract NF data from PDF text content.

    Extracts:
    - Chave de acesso (44 digits)
    - CNPJ do emitente
    - Número da NF
    - Valor total
    - Data de emissão

    Args:
        pdf_content: PDF file content as bytes

    Returns:
        dict: Extracted data or None
    """
    data = {}

    try:
        # Try using pypdf or PyPDF2
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                frappe.logger().warning("pypdf/PyPDF2 not installed. Cannot extract text from PDF.")
                return None

        reader = PdfReader(BytesIO(pdf_content))
        text = ""

        # Extract text from all pages
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not text:
            return None

        # Extract Chave de Acesso (44 digits)
        # Pattern: may have spaces or dots between groups
        chave_patterns = [
            r'(?:chave\s*(?:de\s*)?acesso|NFe)\s*[:\s]*(\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4})',
            r'(\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4}\s*\d{4})',
            r'(\d{44})',
        ]

        for pattern in chave_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                chave = re.sub(r'\s', '', match.group(1))
                if len(chave) == 44 and chave.isdigit():
                    data["chave_de_acesso"] = chave
                    break

        # Extract CNPJ (14 digits, may be formatted)
        cnpj_pattern = r'CNPJ[:\s]*(\d{2}[.\s]?\d{3}[.\s]?\d{3}[/\s]?\d{4}[-\s]?\d{2})'
        match = re.search(cnpj_pattern, text, re.IGNORECASE)
        if match:
            cnpj = re.sub(r'[^\d]', '', match.group(1))
            if len(cnpj) == 14:
                data["emitente_cnpj"] = cnpj

        # Extract NF number
        nf_patterns = [
            r'(?:N[ºo°]\.?\s*|Número\s*(?:da\s*)?(?:NF|Nota)[:\s]*)(\d{1,9})',
            r'NF-e\s*[Nn][ºo°]?\s*(\d{1,9})',
            r'(?:NOTA\s*FISCAL|NF-e)[^\d]*(\d{1,9})',
        ]
        for pattern in nf_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data["numero"] = match.group(1)
                break

        # Extract total value
        valor_patterns = [
            r'(?:VALOR\s*TOTAL|VL\.?\s*TOTAL|TOTAL\s*(?:DA\s*)?NF)[^\d]*R?\$?\s*([\d.,]+)',
            r'(?:TOTAL\s*GERAL)[^\d]*R?\$?\s*([\d.,]+)',
        ]
        for pattern in valor_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                valor_str = match.group(1)
                # Parse Brazilian currency format
                valor_str = valor_str.replace('.', '').replace(',', '.')
                try:
                    data["valor_total"] = float(valor_str)
                except:
                    pass
                break

        # Extract date
        date_patterns = [
            r'(?:DATA\s*(?:DE\s*)?EMISS[ÃA]O|EMISS[ÃA]O)[:\s]*(\d{2}[/.-]\d{2}[/.-]\d{4})',
            r'(\d{2}/\d{2}/\d{4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                # Parse date
                try:
                    from datetime import datetime
                    for fmt in ['%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y']:
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            data["data_emissao"] = dt.date()
                            break
                        except:
                            continue
                except:
                    pass
                break

        # Extract emitente name (Razão Social)
        razao_patterns = [
            r'(?:RAZ[ÃA]O\s*SOCIAL|NOME[/\s]*RAZ[ÃA]O\s*SOCIAL)[:\s]*([A-Z][A-Z\s.,&\-]+?)(?:\s*CNPJ|\s*END|\n)',
        ]
        for pattern in razao_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                razao = match.group(1).strip()
                if len(razao) > 5:
                    data["emitente_razao_social"] = razao[:140]
                break

        # Determine document type from chave de acesso
        if data.get("chave_de_acesso"):
            # Position 21-22 of chave indicates model: 55=NF-e, 57=CT-e, 65=NFC-e
            modelo = data["chave_de_acesso"][20:22]
            if modelo == "55":
                data["document_type"] = "NF-e"
            elif modelo == "57":
                data["document_type"] = "CT-e"
            elif modelo == "65":
                data["document_type"] = "NF-e"  # NFC-e is a variant of NF-e
            else:
                data["document_type"] = "NF-e"  # Default

    except Exception as e:
        frappe.logger().error(f"Error extracting data from PDF: {str(e)}")
        return None

    return data if data.get("chave_de_acesso") else None


def create_nf_from_xml(xml_content, comm, settings):
    """
    Create Nota Fiscal from XML content.

    Args:
        xml_content: XML string
        comm: Communication document
        settings: Nota Fiscal Settings

    Returns:
        bool: True if created/updated
    """
    from brazil_nf.services.xml_parser import NFXMLParser

    parser = NFXMLParser()
    data = parser.parse(xml_content)

    if not data:
        return False

    chave = data.get("chave_de_acesso")

    # Check for duplicates
    if chave:
        existing = frappe.db.exists("Nota Fiscal", {"chave_de_acesso": chave})

        if existing:
            # Update origin flags
            frappe.db.set_value(
                "Nota Fiscal",
                existing,
                {
                    "origin_email": 1,
                    "email_reference": comm.name
                }
            )
            return True

    # Create new Nota Fiscal
    nf_doc = frappe.new_doc("Nota Fiscal")
    nf_doc.company = settings.default_company
    nf_doc.document_type = data.get("document_type", "NF-e")

    # Set origin
    nf_doc.origin_email = 1
    nf_doc.email_reference = comm.name

    # Extract items before setting other fields
    items_data = data.pop("items", [])

    # Populate from parsed data
    for field, value in data.items():
        if hasattr(nf_doc, field) and value is not None:
            setattr(nf_doc, field, value)

    # Add items
    for item_data in items_data:
        nf_doc.append("items", {
            "numero_item": item_data.get("numero_item"),
            "codigo_produto": item_data.get("codigo_produto"),
            "codigo_barras": item_data.get("codigo_barras"),
            "descricao": item_data.get("descricao"),
            "ncm": item_data.get("ncm"),
            "cfop": item_data.get("cfop"),
            "codigo_tributacao_nacional": item_data.get("codigo_tributacao_nacional"),
            "codigo_nbs": item_data.get("codigo_nbs"),
            "unidade": item_data.get("unidade"),
            "quantidade": item_data.get("quantidade"),
            "valor_unitario": item_data.get("valor_unitario"),
            "valor_total": item_data.get("valor_total"),
            "icms_cst": item_data.get("icms_cst"),
            "icms_base_calculo": item_data.get("icms_base_calculo"),
            "icms_aliquota": item_data.get("icms_aliquota"),
            "icms_valor": item_data.get("icms_valor"),
            "iss_base_calculo": item_data.get("iss_base_calculo"),
            "iss_aliquota": item_data.get("iss_aliquota"),
            "iss_valor": item_data.get("iss_valor")
        })

    nf_doc.xml_content = xml_content
    nf_doc.insert(ignore_permissions=True)

    return True


def create_nf_from_pdf_data(pdf_data, pdf_content, attachment, comm, settings):
    """
    Create Nota Fiscal from data extracted from PDF text.

    This is used when PDF doesn't have embedded XML.

    Args:
        pdf_data: Extracted data dict
        pdf_content: Original PDF content
        attachment: File attachment info
        comm: Communication document
        settings: Nota Fiscal Settings

    Returns:
        bool: True if created/updated
    """
    chave = pdf_data.get("chave_de_acesso")

    # Check for duplicates
    if chave:
        existing = frappe.db.exists("Nota Fiscal", {"chave_de_acesso": chave})

        if existing:
            # Update origin flags and attach PDF
            nf_doc = frappe.get_doc("Nota Fiscal", existing)
            nf_doc.origin_email = 1
            nf_doc.email_reference = comm.name

            # Attach PDF if not already attached
            if not nf_doc.xml_file:
                save_pdf_as_attachment(nf_doc.name, pdf_content, attachment["file_name"])

            nf_doc.save(ignore_permissions=True)
            return True

    # Create new Nota Fiscal with limited data
    nf_doc = frappe.new_doc("Nota Fiscal")
    nf_doc.company = settings.default_company
    nf_doc.document_type = pdf_data.get("document_type", "NF-e")

    # Set origin
    nf_doc.origin_email = 1
    nf_doc.email_reference = comm.name

    # Set extracted data
    nf_doc.chave_de_acesso = pdf_data.get("chave_de_acesso")
    nf_doc.emitente_cnpj = pdf_data.get("emitente_cnpj")
    nf_doc.emitente_razao_social = pdf_data.get("emitente_razao_social")
    nf_doc.numero = pdf_data.get("numero")
    nf_doc.valor_total = pdf_data.get("valor_total")
    nf_doc.data_emissao = pdf_data.get("data_emissao")

    # Mark as needing review since we only have partial data
    nf_doc.processing_status = "Parsed"
    nf_doc.processing_error = "Created from PDF text extraction - may need manual review"

    nf_doc.insert(ignore_permissions=True)

    # Attach PDF
    save_pdf_as_attachment(nf_doc.name, pdf_content, attachment["file_name"])

    return True


def save_pdf_as_attachment(nf_name, pdf_content, file_name):
    """
    Save PDF as attachment to Nota Fiscal.

    Args:
        nf_name: Nota Fiscal document name
        pdf_content: PDF file content
        file_name: Original file name
    """
    try:
        from frappe.utils.file_manager import save_file

        save_file(
            file_name,
            pdf_content,
            "Nota Fiscal",
            nf_name,
            is_private=1
        )
    except Exception as e:
        frappe.log_error(f"Error saving PDF attachment: {str(e)}")


def extract_international_invoice(pdf_content):
    """
    Extract international invoice data from PDF.

    Args:
        pdf_content: PDF file content as bytes

    Returns:
        dict: Extracted invoice data or None
    """
    try:
        from brazil_nf.services.invoice_parser import parse_invoice_pdf, is_international_invoice

        # First check if the text looks like international invoice
        try:
            from pypdf import PdfReader
        except ImportError:
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                return None

        from io import BytesIO
        reader = PdfReader(BytesIO(pdf_content))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

        if not is_international_invoice(text):
            return None

        # Parse as international invoice
        return parse_invoice_pdf(pdf_content)

    except Exception as e:
        frappe.logger().error(f"Error extracting international invoice: {str(e)}")
        return None


def create_nf_from_invoice_data(invoice_data, pdf_content, attachment, comm, settings):
    """
    Create Nota Fiscal from international invoice data.

    Args:
        invoice_data: Extracted invoice data dict
        pdf_content: Original PDF content
        attachment: File attachment info
        comm: Communication document
        settings: Nota Fiscal Settings

    Returns:
        bool: True if created/updated
    """
    invoice_number = invoice_data.get("invoice_number")
    vendor_name = invoice_data.get("vendor_name")

    # Check for duplicates by invoice_number + vendor_name
    if invoice_number and vendor_name:
        existing = frappe.db.exists(
            "Nota Fiscal",
            {
                "document_type": "Invoice",
                "invoice_number": invoice_number,
                "vendor_name": vendor_name
            }
        )

        if existing:
            # Update origin flags and attach PDF
            nf_doc = frappe.get_doc("Nota Fiscal", existing)
            nf_doc.origin_email = 1
            nf_doc.email_reference = comm.name
            nf_doc.save(ignore_permissions=True)
            return True

    # Create new Nota Fiscal for international invoice
    nf_doc = frappe.new_doc("Nota Fiscal")
    nf_doc.company = settings.default_company
    nf_doc.document_type = "Invoice"
    nf_doc.naming_series = "INV-.#####"

    # Set origin
    nf_doc.origin_email = 1
    nf_doc.email_reference = comm.name

    # Set invoice-specific fields
    nf_doc.invoice_number = invoice_data.get("invoice_number")
    nf_doc.vendor_name = invoice_data.get("vendor_name")
    nf_doc.vendor_country = invoice_data.get("vendor_country")
    nf_doc.vendor_tax_id = invoice_data.get("vendor_tax_id")
    nf_doc.vendor_email = invoice_data.get("vendor_email")

    # Currency and values
    nf_doc.currency = invoice_data.get("currency", "USD")
    nf_doc.valor_original_currency = invoice_data.get("valor_original_currency")
    nf_doc.valor_total = invoice_data.get("valor_total")

    # Dates
    nf_doc.data_emissao = invoice_data.get("data_emissao")
    nf_doc.billing_period_start = invoice_data.get("billing_period_start")
    nf_doc.billing_period_end = invoice_data.get("billing_period_end")

    # Description
    nf_doc.invoice_description = invoice_data.get("invoice_description")

    # Set numero field from invoice_number for consistency
    nf_doc.numero = invoice_data.get("invoice_number")

    # Mark status
    nf_doc.processing_status = "Parsed"

    try:
        nf_doc.insert(ignore_permissions=True)

        # Attach PDF
        save_pdf_as_attachment(nf_doc.name, pdf_content, attachment["file_name"])

        frappe.logger().info(f"Created international invoice: {nf_doc.name} - {vendor_name} #{invoice_number}")
        return True

    except Exception as e:
        frappe.log_error(f"Error creating invoice: {str(e)}", "Invoice Creation Error")
        return False
