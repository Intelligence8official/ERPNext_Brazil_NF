"""
DF-e Client for SEFAZ integration.

Handles fetching NF-e, CT-e, and NFS-e from SEFAZ DF-e Distribution API.
Adapted from NFSe_WebMonitor/nfse_client.py.
"""

import gzip
import base64
import requests
from datetime import datetime

import frappe
from frappe import _

from brazil_nf.services.cert_utils import CertificateContext
from brazil_nf.services.xml_parser import NFXMLParser


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
        "production": "https://adn.nfse.gov.br/contribuintes/DFe/0",
        "homologation": "https://adn.nfse.gov.br/contribuintes/DFe/0"  # Same for now
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

    for doc_type in doc_types:
        log = create_import_log(
            company_settings.company,
            doc_type,
            "SEFAZ"
        )

        try:
            result = _fetch_documents(company_settings, doc_type, settings, log)
            results[doc_type] = result
            log.mark_completed("Success" if result["created"] > 0 else "Partial")
        except Exception as e:
            log.mark_failed(str(e))
            results[doc_type] = {"status": "error", "message": str(e)}

    return results


def _fetch_documents(company_settings, document_type, settings, log):
    """
    Internal function to fetch documents of a specific type.
    """
    # Get endpoint
    env = settings.sefaz_environment.lower() if settings.sefaz_environment else "production"
    doc_type_key = document_type.lower().replace("-", "")

    if doc_type_key not in SEFAZ_ENDPOINTS:
        raise ValueError(f"Unknown document type: {document_type}")

    endpoint = SEFAZ_ENDPOINTS[doc_type_key].get(env)

    if not endpoint:
        raise ValueError(f"No endpoint for {document_type} in {env}")

    # Get last NSU
    last_nsu = company_settings.get_last_nsu(document_type)

    # Use certificate context for automatic cleanup
    with CertificateContext(company_settings.certificate_file, company_settings.certificate_password) as (cert_path, key_path):
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

    session = requests.Session()
    session.cert = (cert_path, key_path)

    response = session.get(url, timeout=60)
    response.raise_for_status()

    data = response.json()
    documents = data.get("LoteDFe", [])

    created = 0
    skipped = 0

    for doc_data in documents:
        try:
            nsu = doc_data.get("NSU")
            chave = doc_data.get("ChaveAcesso")
            tipo_doc = doc_data.get("TipoDocumento")
            xml_b64 = doc_data.get("ArquivoXml")

            # Update NSU range
            if nsu:
                log.update_nsu_range(nsu)

            # Skip events for now
            if tipo_doc == "EVENTO":
                continue

            # Decode XML
            xml_content = _decode_xml(xml_b64)

            # Check for duplicates
            if chave and frappe.db.exists("Nota Fiscal", {"chave_de_acesso": chave}):
                # Update origin flag
                existing = frappe.get_value("Nota Fiscal", {"chave_de_acesso": chave}, "name")
                frappe.db.set_value("Nota Fiscal", existing, "origin_sefaz", 1)
                skipped += 1
                continue

            # Create Nota Fiscal
            _create_nota_fiscal_from_xml(xml_content, "NFS-e", company_settings, chave)
            created += 1

        except Exception as e:
            frappe.log_error(str(e), f"Error processing NFS-e document")
            log.update_counts(failed=1)

    # Update company settings with last NSU
    if documents:
        last_doc = documents[-1]
        company_settings.update_last_nsu("NFS-e", last_doc.get("NSU", last_nsu))

    log.update_counts(fetched=len(documents), created=created, skipped=skipped)

    return {
        "status": "success",
        "fetched": len(documents),
        "created": created,
        "skipped": skipped
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


def _create_nota_fiscal_from_xml(xml_content, document_type, company_settings, chave=None):
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

    # Populate from parsed data
    for field, value in data.items():
        if hasattr(nf_doc, field) and value is not None:
            setattr(nf_doc, field, value)

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

    env = settings.sefaz_environment.lower() if settings.sefaz_environment else "production"

    # Test NFS-e endpoint (simplest)
    endpoint = SEFAZ_ENDPOINTS["nfse"][env]

    with CertificateContext(company_settings.certificate_file, company_settings.certificate_password) as (cert_path, key_path):
        session = requests.Session()
        session.cert = (cert_path, key_path)

        try:
            response = session.get(f"{endpoint}/0", timeout=30)

            return {
                "status": "success",
                "http_code": response.status_code,
                "message": _("Connection successful")
            }
        except requests.exceptions.SSLError as e:
            return {
                "status": "error",
                "message": _("SSL Error: Certificate may be invalid")
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }
