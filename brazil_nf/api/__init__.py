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


@frappe.whitelist()
def unlink_purchase_invoice(nota_fiscal_name):
    """
    Unlink a Purchase Invoice from a Nota Fiscal.

    Args:
        nota_fiscal_name: Name of the Nota Fiscal document

    Returns:
        dict: Result of the operation
    """
    nf_doc = frappe.get_doc("Nota Fiscal", nota_fiscal_name)

    if not nf_doc.purchase_invoice:
        return {"status": "error", "message": _("No Purchase Invoice linked")}

    purchase_invoice_name = nf_doc.purchase_invoice

    # Clear the reference in Purchase Invoice
    frappe.db.set_value(
        "Purchase Invoice",
        purchase_invoice_name,
        {
            "nota_fiscal": None,
            "chave_de_acesso": None
        },
        update_modified=True
    )

    # Clear the reference in Nota Fiscal
    nf_doc.purchase_invoice = None
    nf_doc.invoice_status = "Pending"
    nf_doc.save()

    return {
        "status": "success",
        "message": _("Purchase Invoice {0} unlinked successfully").format(purchase_invoice_name)
    }


@frappe.whitelist()
def link_purchase_invoice(nota_fiscal_name, purchase_invoice_name):
    """
    Link a Nota Fiscal to an existing Purchase Invoice.

    Args:
        nota_fiscal_name: Name of the Nota Fiscal document
        purchase_invoice_name: Name of the Purchase Invoice document

    Returns:
        dict: Result of the operation
    """
    nf_doc = frappe.get_doc("Nota Fiscal", nota_fiscal_name)

    # Update Purchase Invoice with NF reference
    frappe.db.set_value(
        "Purchase Invoice",
        purchase_invoice_name,
        {
            "nota_fiscal": nota_fiscal_name,
            "chave_de_acesso": nf_doc.chave_de_acesso
        },
        update_modified=True
    )

    # Update Nota Fiscal
    nf_doc.purchase_invoice = purchase_invoice_name
    nf_doc.invoice_status = "Linked"
    nf_doc.save()

    return {"status": "success", "message": _("Purchase Invoice linked successfully")}


@frappe.whitelist()
def find_matching_documents(nota_fiscal_name):
    """
    Find existing Purchase Invoices and Purchase Orders that might match a Nota Fiscal.

    Args:
        nota_fiscal_name: Name of the Nota Fiscal document

    Returns:
        dict: Lists of matching invoices and orders
    """
    from frappe.utils import flt, add_days

    nf_doc = frappe.get_doc("Nota Fiscal", nota_fiscal_name)

    result = {
        "invoices": [],
        "orders": []
    }

    # Value tolerance: 5% or R$10, whichever is greater
    value_tolerance = max(flt(nf_doc.valor_total or 0) * 0.05, 10)
    min_value = flt(nf_doc.valor_total or 0) - value_tolerance
    max_value = flt(nf_doc.valor_total or 0) + value_tolerance

    # Date range: 30 days before and after
    if nf_doc.data_emissao:
        date_from = add_days(nf_doc.data_emissao, -30)
        date_to = add_days(nf_doc.data_emissao, 30)
    else:
        date_from = None
        date_to = None

    # Build supplier filter
    supplier_filter = ""
    if nf_doc.supplier:
        supplier_filter = f"AND supplier = '{nf_doc.supplier}'"

    # Find matching Purchase Invoices
    invoice_query = f"""
        SELECT name, posting_date, grand_total, bill_no, supplier, nota_fiscal
        FROM `tabPurchase Invoice`
        WHERE docstatus < 2
        {supplier_filter}
        AND grand_total BETWEEN %(min_value)s AND %(max_value)s
        {"AND posting_date BETWEEN %(date_from)s AND %(date_to)s" if date_from else ""}
        ORDER BY ABS(grand_total - %(value)s) ASC
        LIMIT 10
    """

    params = {
        "min_value": min_value,
        "max_value": max_value,
        "value": nf_doc.valor_total or 0
    }
    if date_from:
        params["date_from"] = date_from
        params["date_to"] = date_to

    result["invoices"] = frappe.db.sql(invoice_query, params, as_dict=True)

    # Find matching Purchase Orders
    order_query = f"""
        SELECT name, transaction_date, grand_total, supplier, status
        FROM `tabPurchase Order`
        WHERE docstatus < 2
        {supplier_filter}
        AND grand_total BETWEEN %(min_value)s AND %(max_value)s
        {"AND transaction_date BETWEEN %(date_from)s AND %(date_to)s" if date_from else ""}
        ORDER BY ABS(grand_total - %(value)s) ASC
        LIMIT 10
    """

    result["orders"] = frappe.db.sql(order_query, params, as_dict=True)

    return result


@frappe.whitelist()
def batch_process(documents):
    """
    Process multiple Nota Fiscal documents in batch.

    Args:
        documents: List of Nota Fiscal document names

    Returns:
        dict: Processing results summary
    """
    import json
    from brazil_nf.services.processor import NFProcessor

    if isinstance(documents, str):
        documents = json.loads(documents)

    results = {
        "processed": 0,
        "completed": 0,
        "errors": 0,
        "skipped": 0,
        "details": []
    }

    processor = NFProcessor()

    for doc_name in documents:
        try:
            nf_doc = frappe.get_doc("Nota Fiscal", doc_name)

            # Skip cancelled documents
            if nf_doc.cancelada or nf_doc.processing_status == "Cancelled":
                results["skipped"] += 1
                results["details"].append({
                    "name": doc_name,
                    "status": "skipped",
                    "message": _("Document is cancelled")
                })
                continue

            # Skip already completed documents
            if nf_doc.processing_status == "Completed":
                results["skipped"] += 1
                results["details"].append({
                    "name": doc_name,
                    "status": "skipped",
                    "message": _("Already completed")
                })
                continue

            result = processor.process(nf_doc)
            results["processed"] += 1

            if result.get("processing_status") == "Completed":
                results["completed"] += 1
                results["details"].append({
                    "name": doc_name,
                    "status": "completed"
                })
            else:
                results["details"].append({
                    "name": doc_name,
                    "status": result.get("processing_status", "Error"),
                    "message": nf_doc.processing_error if hasattr(nf_doc, "processing_error") else None
                })

        except Exception as e:
            results["errors"] += 1
            results["details"].append({
                "name": doc_name,
                "status": "error",
                "message": str(e)
            })
            frappe.log_error(str(e), f"Batch Processing Error: {doc_name}")

    return results
