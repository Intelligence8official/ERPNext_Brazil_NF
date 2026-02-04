"""
DF-e Client for SEFAZ integration.

Handles fetching NF-e, CT-e, and NFS-e from SEFAZ DF-e Distribution API.
Adapted from NFSe_WebMonitor/nfse_client.py.
"""

import gzip
import base64
import requests
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime

# SEFAZ rate limit: must wait 1 hour when no new documents
SEFAZ_WAIT_HOURS = 1

from brazil_nf.services.cert_utils import CertificateContext
from brazil_nf.services.xml_parser import NFXMLParser


def _check_rate_limit(company_settings, document_type):
    """
    Check if fetching is allowed based on SEFAZ rate limits.

    SEFAZ requires waiting 1 hour after receiving an empty response
    (no new documents) before making another request.

    Returns:
        tuple: (allowed: bool, wait_minutes: int, message: str)
    """
    field_map = {
        "NF-e": "last_empty_response_nfe",
        "CT-e": "last_empty_response_cte",
        "NFS-e": "last_empty_response_nfse"
    }

    field = field_map.get(document_type)
    if not field:
        return True, 0, ""

    last_empty = getattr(company_settings, field, None)
    if not last_empty:
        return True, 0, ""

    last_empty_dt = get_datetime(last_empty)
    wait_until = last_empty_dt + timedelta(hours=SEFAZ_WAIT_HOURS)
    now = now_datetime()

    if now < wait_until:
        wait_minutes = int((wait_until - now).total_seconds() / 60)
        return False, wait_minutes, _(
            "SEFAZ rate limit: must wait {0} more minutes. "
            "Last empty response was at {1}."
        ).format(wait_minutes, last_empty_dt.strftime("%H:%M:%S"))

    return True, 0, ""


def _update_rate_limit(company_settings, document_type, had_documents):
    """
    Update rate limit tracking after a fetch using direct DB update.

    If no documents were returned, record the time so we know to wait 1 hour.
    If documents were returned, clear the empty response time.
    """
    field_map = {
        "NF-e": "last_empty_response_nfe",
        "CT-e": "last_empty_response_cte",
        "NFS-e": "last_empty_response_nfse"
    }

    field = field_map.get(document_type)
    if not field:
        return

    if had_documents:
        # Clear the empty response time - we got documents
        new_value = None
    else:
        # Record that we got an empty response - must wait 1 hour
        new_value = now_datetime()
        frappe.logger().info(
            f"SEFAZ rate limit: No documents for {document_type}. "
            f"Must wait {SEFAZ_WAIT_HOURS} hour(s) before next fetch."
        )

    # Use direct DB update to avoid document modification conflicts
    frappe.db.set_value(
        "NF Company Settings",
        company_settings.name,
        field,
        new_value,
        update_modified=False
    )
    # Update local attribute for consistency
    setattr(company_settings, field, new_value)


# SEFAZ DF-e Distribution endpoints
SEFAZ_ENDPOINTS = {
    "nfe": {
        "production": "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx",
        "homologation": "https://hom.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
    },
    "cte": {
        "production": "https://www1.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx",
        "homologation": "https://hom.cte.fazenda.gov.br/CTeDistribuicaoDFe/CTeDistribuicaoDFe.asmx"
    },
    "nfse": {
        "production": "https://adn.nfse.gov.br/contribuintes/DFe",
        "homologation": "https://adn.producaorestrita.nfse.gov.br/contribuintes/DFe"
    }
}


def scheduled_fetch():
    """
    Scheduled job to fetch documents from SEFAZ for all enabled companies.
    """
    settings = frappe.get_single("Nota Fiscal Settings")

    if not settings.enabled:
        return

    from brazil_nf.brazil_nf.doctype.nf_company_settings.nf_company_settings import get_all_enabled_companies

    companies = get_all_enabled_companies()

    for company_data in companies:
        try:
            fetch_documents_for_company(company_data["name"])
        except Exception as e:
            frappe.log_error(str(e), f"SEFAZ Fetch Error: {company_data['company']}")


def fetch_documents_for_company(company_settings_name, document_type=None):
    """
    Fetch documents from SEFAZ for a specific company.

    Args:
        company_settings_name: Name of NF Company Settings document
        document_type: Optional specific document type (NF-e, CT-e, NFS-e)

    Returns:
        dict: Fetch results
    """
    from brazil_nf.brazil_nf.doctype.nf_company_settings.nf_company_settings import get_company_settings
    from brazil_nf.brazil_nf.doctype.nf_import_log.nf_import_log import create_import_log

    company_settings = frappe.get_doc("NF Company Settings", company_settings_name)
    settings = frappe.get_single("Nota Fiscal Settings")

    if not company_settings.certificate_valid:
        return {"status": "error", "message": _("Certificate not valid")}

    # Determine which document types to fetch
    doc_types = []

    if document_type:
        doc_types = [document_type]
    else:
        if settings.nfe_enabled:
            doc_types.append("NF-e")
        if settings.cte_enabled:
            doc_types.append("CT-e")
        if settings.nfse_enabled:
            doc_types.append("NFS-e")

    results = {}

    # Get environment for display
    env = _get_sefaz_environment(company_settings, settings)
    env_display = "Produção" if env == "production" else "Homologação"

    for doc_type in doc_types:
        # Check rate limit before fetching
        allowed, wait_minutes, rate_limit_msg = _check_rate_limit(company_settings, doc_type)

        if not allowed:
            frappe.logger().info(f"Skipping {doc_type} fetch: {rate_limit_msg}")
            results[doc_type] = {
                "status": "rate_limited",
                "fetched": 0,
                "created": 0,
                "skipped": 0,
                "message": rate_limit_msg,
                "wait_minutes": wait_minutes
            }
            continue

        log = create_import_log(
            company_settings.company,
            doc_type,
            "SEFAZ"
        )

        try:
            result = _fetch_documents(company_settings, doc_type, settings, log)
            result["environment"] = env_display  # Add environment to result
            results[doc_type] = result

            # Update rate limit tracking (uses direct DB update)
            had_documents = result.get("fetched", 0) > 0
            _update_rate_limit(company_settings, doc_type, had_documents)

            log.mark_completed("Success" if result["created"] > 0 else "Partial")
        except Exception as e:
            log.mark_failed(str(e))
            results[doc_type] = {"status": "error", "message": str(e), "environment": env_display}

    return results


def _get_sefaz_environment(company_settings, global_settings):
    """
    Get SEFAZ environment, prioritizing company-level setting over global.

    Returns:
        str: 'production' or 'homologation'
    """
    # Company-level setting takes priority
    if company_settings.sefaz_environment:
        return company_settings.sefaz_environment.lower()

    # Fall back to global setting
    if global_settings.sefaz_environment:
        return global_settings.sefaz_environment.lower()

    # Default to production
    return "production"


def _fetch_documents(company_settings, document_type, settings, log):
    """
    Internal function to fetch documents of a specific type.
    """
    # Get endpoint - company setting takes priority over global
    env = _get_sefaz_environment(company_settings, settings)
    doc_type_key = document_type.lower().replace("-", "")

    if doc_type_key not in SEFAZ_ENDPOINTS:
        raise ValueError(f"Unknown document type: {document_type}")

    endpoint = SEFAZ_ENDPOINTS[doc_type_key].get(env)

    if not endpoint:
        raise ValueError(f"No endpoint for {document_type} in {env}")

    # Get last NSU
    last_nsu = company_settings.get_last_nsu(document_type)

    # Get decrypted password
    certificate_password = company_settings.get_certificate_password()

    # Use certificate context for automatic cleanup
    with CertificateContext(company_settings.certificate_file, certificate_password) as (cert_path, key_path):
        # For NFS-e (REST API)
        if document_type == "NFS-e":
            return _fetch_nfse_documents(endpoint, cert_path, key_path, last_nsu, company_settings, log)
        else:
            # For NF-e and CT-e (SOAP API)
            return _fetch_dfe_documents(endpoint, cert_path, key_path, last_nsu, document_type, company_settings, log)


def _fetch_nfse_documents(endpoint, cert_path, key_path, last_nsu, company_settings, log):
    """
    Fetch NFS-e documents using REST API.

    Adapted from NFSe_WebMonitor/nfse_client.py
    """
    url = f"{endpoint}/{last_nsu}"

    frappe.logger().info(f"NFS-e Fetch: URL={url}, NSU={last_nsu}")

    session = requests.Session()
    session.cert = (cert_path, key_path)

    response = session.get(url, timeout=60)

    frappe.logger().info(f"NFS-e Fetch: HTTP Status={response.status_code}")
    frappe.logger().info(f"NFS-e Fetch: Response={response.text[:1000] if response.text else 'empty'}")

    response.raise_for_status()

    data = response.json()

    # Log API response status
    status = data.get("StatusProcessamento", "unknown")
    erros = data.get("Erros", [])
    alertas = data.get("Alertas", [])
    frappe.logger().info(f"NFS-e Fetch: StatusProcessamento={status}")
    if erros:
        frappe.logger().warning(f"NFS-e Fetch: Erros={erros}")
    if alertas:
        frappe.logger().info(f"NFS-e Fetch: Alertas={alertas}")

    documents = data.get("LoteDFe", [])
    frappe.logger().info(f"NFS-e Fetch: Found {len(documents)} documents in LoteDFe")

    # Log document structure for debugging
    if documents:
        sample_doc = documents[0]
        frappe.logger().info(f"NFS-e Fetch: Sample document keys: {list(sample_doc.keys())}")
        frappe.logger().info(f"NFS-e Fetch: Sample NSU value: {sample_doc.get('NSU')} (type: {type(sample_doc.get('NSU')).__name__})")

    created = 0
    skipped = 0
    events_processed = 0

    # Track NSU range for batch update at end
    nsu_values = []

    for doc_data in documents:
        try:
            nsu = doc_data.get("NSU")
            chave = doc_data.get("ChaveAcesso")
            tipo_doc = doc_data.get("TipoDocumento")
            tipo_evento = doc_data.get("TipoEvento")
            xml_b64 = doc_data.get("ArquivoXml")

            # Track NSU for range update
            if nsu:
                nsu_values.append(nsu)

            # Handle events (cancellation, etc.)
            if tipo_doc == "EVENTO":
                _process_evento(chave, tipo_evento, xml_b64)
                events_processed += 1
                continue

            # Decode XML
            xml_content = _decode_xml(xml_b64)

            # Check for duplicates by chave_de_acesso
            if chave and frappe.db.exists("Nota Fiscal", {"chave_de_acesso": chave}):
                # Update origin flag
                existing = frappe.get_value("Nota Fiscal", {"chave_de_acesso": chave}, "name")
                frappe.db.set_value("Nota Fiscal", existing, "origin_sefaz", 1)
                skipped += 1
                frappe.logger().info(f"NFS-e Fetch: Skipped duplicate by chave: {chave}")
                continue

            # Also check by NSU to prevent duplicates if chave is missing
            if nsu and frappe.db.exists("Nota Fiscal", {"nsu": str(nsu), "company": company_settings.company}):
                skipped += 1
                frappe.logger().info(f"NFS-e Fetch: Skipped duplicate by NSU: {nsu}")
                continue

            # Create Nota Fiscal
            _create_nota_fiscal_from_xml(xml_content, "NFS-e", company_settings, chave, nsu)
            created += 1

        except Exception as e:
            frappe.log_error(str(e), f"Error processing NFS-e document")
            log.update_counts(failed=1)

    # Update NSU range once at the end (more efficient)
    if nsu_values:
        log.first_nsu = log.first_nsu or str(min(nsu_values))
        log.last_nsu = str(max(nsu_values))
        log.save(ignore_permissions=True)

    # Update company settings with last NSU
    max_nsu = int(last_nsu or 0)
    nsu_list = []

    if documents:
        # Find the highest NSU from all documents
        for doc in documents:
            doc_nsu = doc.get("NSU")
            frappe.logger().info(f"NFS-e Fetch: Document NSU = {doc_nsu} (type: {type(doc_nsu).__name__})")
            if doc_nsu is not None:
                try:
                    doc_nsu_int = int(doc_nsu)
                    nsu_list.append(doc_nsu_int)
                    if doc_nsu_int > max_nsu:
                        max_nsu = doc_nsu_int
                except (ValueError, TypeError) as e:
                    frappe.logger().warning(f"NFS-e Fetch: Could not parse NSU {doc_nsu}: {e}")

        frappe.logger().info(f"NFS-e Fetch: NSU list = {nsu_list}, max = {max_nsu}")

        if max_nsu > int(last_nsu or 0):
            frappe.logger().info(f"NFS-e Fetch: Updating NSU from {last_nsu} to {max_nsu}")
            company_settings.update_last_nsu("NFS-e", str(max_nsu))
        else:
            frappe.logger().info(f"NFS-e Fetch: NSU not updated (max {max_nsu} <= current {last_nsu})")

    log.update_counts(fetched=len(documents), created=created, skipped=skipped)

    return {
        "status": "success",
        "fetched": len(documents),
        "created": created,
        "skipped": skipped,
        "events": events_processed,
        "sefaz_status": status,
        "nsu_used": last_nsu
    }


def _fetch_dfe_documents(endpoint, cert_path, key_path, last_nsu, document_type, company_settings, log):
    """
    Fetch NF-e or CT-e documents using SOAP API.

    Note: This is a placeholder - actual implementation would use
    zeep or another SOAP library for the SEFAZ web services.
    """
    # TODO: Implement SOAP-based NF-e/CT-e distribution fetch
    # This would require:
    # 1. Build SOAP envelope with distDFeInt request
    # 2. Sign the request with digital certificate
    # 3. Send to SEFAZ endpoint
    # 4. Parse response and extract documents

    frappe.logger().warning(
        f"NF-e/CT-e SOAP fetch not yet implemented. "
        f"Document type: {document_type}, Endpoint: {endpoint}"
    )

    return {
        "status": "not_implemented",
        "fetched": 0,
        "created": 0,
        "skipped": 0,
        "message": "SOAP-based fetch not yet implemented"
    }


def _decode_xml(xml_b64):
    """
    Decode base64-encoded gzipped XML.
    """
    if not xml_b64:
        return None

    # Decode base64
    compressed = base64.b64decode(xml_b64)

    # Decompress gzip
    try:
        xml_bytes = gzip.decompress(compressed)
    except gzip.BadGzipFile:
        # Not gzipped, try as plain base64
        xml_bytes = compressed

    return xml_bytes.decode("utf-8")


def _process_evento(chave_acesso, tipo_evento, xml_b64):
    """
    Process an event (cancellation, correction, etc.) for an existing NF.

    Args:
        chave_acesso: Access key of the related NF
        tipo_evento: Event type (e.g., "Cancelamento", "101101")
        xml_b64: Base64-encoded event XML
    """
    if not chave_acesso:
        return

    # Find the related Nota Fiscal
    nf_name = frappe.db.get_value("Nota Fiscal", {"chave_de_acesso": chave_acesso}, "name")

    if not nf_name:
        frappe.logger().warning(f"Event received for unknown NF: {chave_acesso}")
        return

    # Decode event XML for details
    xml_content = _decode_xml(xml_b64) if xml_b64 else None

    # Determine event type and process accordingly
    tipo_evento_lower = (tipo_evento or "").lower()

    # Cancellation event codes/names
    cancellation_indicators = [
        "cancelamento", "cancel", "101101", "101", "e101101"
    ]

    is_cancellation = any(ind in tipo_evento_lower for ind in cancellation_indicators)

    if is_cancellation:
        # Get full NF document to check for linked documents
        nf_doc = frappe.get_doc("Nota Fiscal", nf_name)

        # Check for linked Purchase Invoice
        linked_docs_issues = []
        if nf_doc.purchase_invoice:
            pi_result = _handle_linked_purchase_invoice(nf_doc.purchase_invoice, nf_name)
            if not pi_result["success"]:
                linked_docs_issues.append(pi_result)

        # Mark the NF as cancelled
        frappe.db.set_value(
            "Nota Fiscal",
            nf_name,
            {
                "cancelada": 1,
                "status_sefaz": "Cancelada",
                "processing_status": "Cancelled",
                "data_cancelamento": now_datetime()
            },
            update_modified=True
        )

        frappe.logger().info(f"NF {nf_name} marked as cancelled (event: {tipo_evento})")

        # Store event XML if available
        if xml_content:
            try:
                nf_doc.reload()
                nf_doc.append("eventos", {
                    "tipo_evento": "Cancelamento",
                    "codigo_evento": tipo_evento,
                    "data_evento": now_datetime(),
                    "descricao": "Cancelamento de NFS-e",
                    "xml_evento": xml_content
                })
                nf_doc.save(ignore_permissions=True)
            except Exception as e:
                frappe.logger().warning(f"Could not add event to NF {nf_name}: {e}")

        # Send alert email if there were issues with linked documents
        if linked_docs_issues:
            _send_cancellation_alert(nf_doc, linked_docs_issues)
    else:
        frappe.logger().info(f"Event {tipo_evento} received for NF {nf_name} (not processed)")


def _handle_linked_purchase_invoice(pi_name, nf_name):
    """
    Handle a linked Purchase Invoice when the NF is cancelled.

    Attempts to cancel the Purchase Invoice if possible.

    Args:
        pi_name: Name of the Purchase Invoice
        nf_name: Name of the Nota Fiscal

    Returns:
        dict: Result with success flag and message
    """
    try:
        pi_doc = frappe.get_doc("Purchase Invoice", pi_name)

        # Check if invoice is already cancelled
        if pi_doc.docstatus == 2:
            return {
                "success": True,
                "document_type": "Purchase Invoice",
                "document_name": pi_name,
                "message": "Already cancelled"
            }

        # Check if invoice is submitted
        if pi_doc.docstatus == 1:
            # Try to cancel it
            try:
                pi_doc.flags.ignore_permissions = True
                pi_doc.cancel()
                frappe.logger().info(f"Purchase Invoice {pi_name} cancelled due to NF {nf_name} cancellation")
                return {
                    "success": True,
                    "document_type": "Purchase Invoice",
                    "document_name": pi_name,
                    "message": "Cancelled successfully"
                }
            except Exception as e:
                # Cancellation failed - likely due to linked GL entries, payments, etc.
                frappe.logger().warning(
                    f"Could not cancel Purchase Invoice {pi_name}: {e}"
                )
                return {
                    "success": False,
                    "document_type": "Purchase Invoice",
                    "document_name": pi_name,
                    "message": str(e),
                    "action_required": "Manual cancellation required"
                }
        else:
            # Invoice is in draft - just delete it
            try:
                frappe.delete_doc("Purchase Invoice", pi_name, ignore_permissions=True)
                frappe.logger().info(f"Draft Purchase Invoice {pi_name} deleted due to NF {nf_name} cancellation")
                return {
                    "success": True,
                    "document_type": "Purchase Invoice",
                    "document_name": pi_name,
                    "message": "Draft deleted"
                }
            except Exception as e:
                return {
                    "success": False,
                    "document_type": "Purchase Invoice",
                    "document_name": pi_name,
                    "message": str(e),
                    "action_required": "Manual deletion required"
                }

    except Exception as e:
        frappe.logger().error(f"Error handling linked Purchase Invoice {pi_name}: {e}")
        return {
            "success": False,
            "document_type": "Purchase Invoice",
            "document_name": pi_name,
            "message": str(e),
            "action_required": "Check document status"
        }


def _send_cancellation_alert(nf_doc, issues):
    """
    Send email alert when a cancellation event cannot fully process linked documents.

    Args:
        nf_doc: The Nota Fiscal document
        issues: List of issues with linked documents
    """
    settings = frappe.get_single("Nota Fiscal Settings")

    # Check if alerts are enabled and email is configured
    if not settings.send_cancellation_alerts:
        return

    if not settings.alert_email:
        frappe.logger().warning("Cancellation alert not sent: No alert email configured")
        return

    # Build email content
    subject = _("Action Required: NF Cancellation - {0}").format(nf_doc.name)

    issues_html = ""
    for issue in issues:
        issues_html += f"""
        <tr>
            <td>{issue.get('document_type', '')}</td>
            <td>{issue.get('document_name', '')}</td>
            <td>{issue.get('message', '')}</td>
            <td><strong>{issue.get('action_required', '')}</strong></td>
        </tr>
        """

    message = f"""
    <h3>Nota Fiscal Cancellation Alert</h3>

    <p>A Nota Fiscal was cancelled at SEFAZ but some linked documents could not be cancelled automatically.</p>

    <h4>Nota Fiscal Details:</h4>
    <ul>
        <li><strong>Document:</strong> {nf_doc.name}</li>
        <li><strong>Chave de Acesso:</strong> {nf_doc.chave_de_acesso or '-'}</li>
        <li><strong>Supplier:</strong> {nf_doc.emitente_razao_social or nf_doc.emitente_cnpj or '-'}</li>
        <li><strong>Value:</strong> R$ {nf_doc.valor_total or 0:,.2f}</li>
    </ul>

    <h4>Documents Requiring Action:</h4>
    <table border="1" cellpadding="5" cellspacing="0" style="border-collapse: collapse;">
        <tr style="background-color: #f0f0f0;">
            <th>Document Type</th>
            <th>Document</th>
            <th>Error</th>
            <th>Action Required</th>
        </tr>
        {issues_html}
    </table>

    <p>Please review and take the necessary action to cancel or adjust these linked documents.</p>

    <p><a href="{frappe.utils.get_url()}/app/nota-fiscal/{nf_doc.name}">View Nota Fiscal</a></p>
    """

    try:
        frappe.sendmail(
            recipients=[settings.alert_email],
            subject=subject,
            message=message,
            now=True
        )
        frappe.logger().info(f"Cancellation alert sent for NF {nf_doc.name}")
    except Exception as e:
        frappe.logger().error(f"Failed to send cancellation alert: {e}")


def _create_nota_fiscal_from_xml(xml_content, document_type, company_settings, chave=None, nsu=None):
    """
    Create a Nota Fiscal document from XML content.
    """
    parser = NFXMLParser()
    data = parser.parse(xml_content)

    if not data:
        raise ValueError("Failed to parse XML")

    settings = frappe.get_single("Nota Fiscal Settings")

    nf_doc = frappe.new_doc("Nota Fiscal")
    nf_doc.document_type = document_type
    nf_doc.company = company_settings.company
    nf_doc.origin_sefaz = 1

    # Set chave if provided
    if chave:
        nf_doc.chave_de_acesso = chave

    # Set NSU if provided (for duplicate detection)
    if nsu:
        nf_doc.nsu = str(nsu)

    # Extract items before processing other fields
    items_data = data.pop("items", [])

    # Populate from parsed data (excluding items which need special handling)
    for field, value in data.items():
        if hasattr(nf_doc, field) and value is not None:
            setattr(nf_doc, field, value)

    # Add items to child table
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

    return nf_doc.name


def test_sefaz_connection(company_settings_name):
    """
    Test connection to SEFAZ using company certificate.

    Returns:
        dict: Test result
    """
    company_settings = frappe.get_doc("NF Company Settings", company_settings_name)
    settings = frappe.get_single("Nota Fiscal Settings")

    # Get environment - company setting takes priority
    env = _get_sefaz_environment(company_settings, settings)
    env_display = "Produção" if env == "production" else "Homologação"

    # Test NFS-e endpoint (simplest)
    endpoint = SEFAZ_ENDPOINTS["nfse"][env]

    # Get decrypted password
    certificate_password = company_settings.get_certificate_password()

    with CertificateContext(company_settings.certificate_file, certificate_password) as (cert_path, key_path):
        session = requests.Session()
        session.cert = (cert_path, key_path)

        try:
            response = session.get(f"{endpoint}/0", timeout=30)

            return {
                "status": "success",
                "http_code": response.status_code,
                "message": _("Connection successful"),
                "environment": env_display,
                "endpoint": endpoint
            }
        except requests.exceptions.SSLError as e:
            return {
                "status": "error",
                "message": _("SSL Error: Certificate may be invalid"),
                "environment": env_display
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }


def send_error_alert(subject, error_message, context=None):
    """
    Send error alert email when processing errors occur.

    Args:
        subject: Email subject
        error_message: The error message/traceback
        context: Optional dict with additional context (nf_name, document_type, etc.)
    """
    settings = frappe.get_single("Nota Fiscal Settings")

    # Check if error alerts are enabled and email is configured
    if not settings.send_error_alerts:
        return

    if not settings.alert_email:
        frappe.logger().warning("Error alert not sent: No alert email configured")
        return

    context = context or {}

    # Build context HTML
    context_html = ""
    if context:
        context_items = ""
        for key, value in context.items():
            context_items += f"<li><strong>{key}:</strong> {value}</li>"
        context_html = f"<h4>Context:</h4><ul>{context_items}</ul>"

    message = f"""
    <h3>Brazil NF Processing Error</h3>

    {context_html}

    <h4>Error Details:</h4>
    <pre style="background-color: #f5f5f5; padding: 10px; border: 1px solid #ddd; overflow-x: auto;">
{error_message}
    </pre>

    <p>Please review the error log for more details.</p>

    <p><a href="{frappe.utils.get_url()}/app/error-log">View Error Log</a></p>
    """

    try:
        frappe.sendmail(
            recipients=[settings.alert_email],
            subject=f"[Brazil NF Error] {subject}",
            message=message,
            now=True
        )
        frappe.logger().info(f"Error alert sent: {subject}")
    except Exception as e:
        frappe.logger().error(f"Failed to send error alert: {e}")
