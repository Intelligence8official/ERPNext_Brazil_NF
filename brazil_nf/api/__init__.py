# Brazil NF API Endpoints
import frappe
from frappe import _


@frappe.whitelist()
def fetch_documents(company=None, document_type=None):
    """
    Manually trigger document fetch from SEFAZ.

    Args:
        company: Company name (optional, fetches for all if not specified)
        document_type: NF-e, CT-e, or NFS-e (optional, fetches all types if not specified)

    Returns:
        dict: Result of fetch operation
    """
    from brazil_nf.services.dfe_client import fetch_documents_for_company

    if company:
        return fetch_documents_for_company(company, document_type)
    else:
        from brazil_nf.services.dfe_client import scheduled_fetch
        scheduled_fetch()
        return {"status": "success", "message": _("Fetch initiated for all companies")}


@frappe.whitelist()
def process_nota_fiscal(nota_fiscal_name):
    """
    Manually trigger processing of a Nota Fiscal.

    Args:
        nota_fiscal_name: Name of the Nota Fiscal document

    Returns:
        dict: Processing result
    """
    from brazil_nf.services.processor import NFProcessor

    nf_doc = frappe.get_doc("Nota Fiscal", nota_fiscal_name)
    processor = NFProcessor()
    result = processor.process(nf_doc)

    return result


@frappe.whitelist()
def link_purchase_order(nota_fiscal_name, purchase_order_name):
    """
    Manually link a Nota Fiscal to a Purchase Order.

    Args:
        nota_fiscal_name: Name of the Nota Fiscal document
        purchase_order_name: Name of the Purchase Order document

    Returns:
        dict: Link result
    """
    nf_doc = frappe.get_doc("Nota Fiscal", nota_fiscal_name)
    nf_doc.purchase_order = purchase_order_name
    nf_doc.po_status = "Linked"
    nf_doc.save()

    return {"status": "success", "message": _("Purchase Order linked successfully")}


@frappe.whitelist()
def create_purchase_invoice(nota_fiscal_name, submit=False):
    """
    Create a Purchase Invoice from a Nota Fiscal.

    Args:
        nota_fiscal_name: Name of the Nota Fiscal document
        submit: Whether to submit the invoice after creation

    Returns:
        dict: Created invoice details
    """
    from brazil_nf.services.invoice_creator import InvoiceCreator

    nf_doc = frappe.get_doc("Nota Fiscal", nota_fiscal_name)
    creator = InvoiceCreator()
    invoice_name = creator.create_purchase_invoice(nf_doc, submit=submit)

    return {"status": "success", "invoice": invoice_name}


@frappe.whitelist()
def validate_chave_acesso(chave):
    """
    Validate a chave de acesso (access key).

    Args:
        chave: 44-digit access key

    Returns:
        dict: Validation result with parsed components
    """
    from brazil_nf.utils.chave_acesso import validate_chave_acesso as validate, parse_chave_acesso

    is_valid = validate(chave)
    components = parse_chave_acesso(chave) if is_valid else None

    return {
        "valid": is_valid,
        "components": components
    }


@frappe.whitelist()
def get_enabled_companies():
    """
    Get list of companies with valid certificates for SEFAZ integration.

    Returns:
        list: List of company settings with sync info
    """
    companies = frappe.get_all(
        "NF Company Settings",
        filters={"certificate_valid": 1},
        fields=[
            "name", "company", "cnpj", "sync_enabled",
            "last_nsu_nfse", "last_sync", "sefaz_environment"
        ]
    )

    return companies


@frappe.whitelist()
def test_company_connection(company_settings_name):
    """
    Test SEFAZ connection for a specific company.

    Args:
        company_settings_name: Name of NF Company Settings document

    Returns:
        dict: Test result
    """
    from brazil_nf.services.dfe_client import test_sefaz_connection
    return test_sefaz_connection(company_settings_name)


@frappe.whitelist()
def fetch_for_company(company_settings_name, document_type=None):
    """
    Fetch documents from SEFAZ for a specific company.

    Args:
        company_settings_name: Name of NF Company Settings document
        document_type: Optional specific document type

    Returns:
        dict: Fetch results
    """
    from brazil_nf.services.dfe_client import fetch_documents_for_company
    return fetch_documents_for_company(company_settings_name, document_type)
