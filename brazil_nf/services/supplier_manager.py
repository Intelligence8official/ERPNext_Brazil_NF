"""
Supplier management service for auto-creation and linking.
"""

import frappe
from frappe import _

from brazil_nf.utils.cnpj import clean_cnpj, format_cnpj


class SupplierManager:
    """
    Manages supplier creation and linking for Nota Fiscal documents.
    """

    def __init__(self):
        self.settings = frappe.get_single("Nota Fiscal Settings")

    def process_nf_supplier(self, nf_doc):
        """
        Process supplier for a Nota Fiscal.

        1. Search existing supplier by CNPJ
        2. If found: link and return status="Linked"
        3. If not found and auto_create enabled: create supplier
        4. If not found and auto_create disabled: return status="Not Found"

        Returns:
            tuple: (supplier_name, status, message)
        """
        if not nf_doc.emitente_cnpj:
            return None, "Failed", _("No CNPJ in document")

        cnpj = clean_cnpj(nf_doc.emitente_cnpj)

        # Search for existing supplier by CNPJ
        existing = self.find_supplier_by_cnpj(cnpj)

        if existing:
            return existing, "Linked", _("Supplier found by CNPJ")

        # Auto-create if enabled
        if self.settings.auto_create_supplier:
            try:
                supplier_name = self.create_supplier(nf_doc)
                return supplier_name, "Created", _("Supplier created automatically")
            except Exception as e:
                frappe.log_error(str(e), "Supplier Creation Error")
                return None, "Failed", str(e)

        return None, "Not Found", _("Supplier not found and auto-create disabled")

    def find_supplier_by_cnpj(self, cnpj):
        """
        Find a supplier by CNPJ.

        Args:
            cnpj: Clean CNPJ (14 digits)

        Returns:
            str: Supplier name or None
        """
        cnpj = clean_cnpj(cnpj)

        # 1. Search in tax_id field - exact match with clean CNPJ
        suppliers = frappe.get_all(
            "Supplier",
            filters={"tax_id": cnpj},
            pluck="name",
            limit=1
        )
        if suppliers:
            return suppliers[0]

        # 2. Search with formatted CNPJ
        formatted = format_cnpj(cnpj)
        suppliers = frappe.get_all(
            "Supplier",
            filters={"tax_id": formatted},
            pluck="name",
            limit=1
        )
        if suppliers:
            return suppliers[0]

        # 3. Search with LIKE (partial match) - clean CNPJ
        suppliers = frappe.get_all(
            "Supplier",
            filters={"tax_id": ["like", f"%{cnpj}%"]},
            pluck="name",
            limit=1
        )
        if suppliers:
            return suppliers[0]

        # 4. Search using SQL to handle different formats
        # This catches cases where CNPJ might be stored with different separators
        result = frappe.db.sql("""
            SELECT name FROM `tabSupplier`
            WHERE REPLACE(REPLACE(REPLACE(tax_id, '.', ''), '/', ''), '-', '') = %s
            LIMIT 1
        """, (cnpj,), as_dict=True)

        if result:
            return result[0].name

        # 5. Search in past Purchase Invoices to find supplier by CNPJ in custom fields
        invoices = frappe.db.sql("""
            SELECT DISTINCT supplier FROM `tabPurchase Invoice`
            WHERE (chave_de_acesso LIKE %s OR bill_no LIKE %s)
            AND docstatus IN (0, 1)
            LIMIT 1
        """, (f"%{cnpj}%", f"%{cnpj}%"), as_dict=True)

        if invoices:
            return invoices[0].supplier

        return None

    def create_supplier(self, nf_doc):
        """
        Create a new supplier from Nota Fiscal data.

        Args:
            nf_doc: Nota Fiscal document

        Returns:
            str: Created supplier name
        """
        cnpj = clean_cnpj(nf_doc.emitente_cnpj)
        supplier_name = nf_doc.emitente_razao_social or f"Supplier {format_cnpj(cnpj)}"

        supplier = frappe.new_doc("Supplier")
        supplier.supplier_name = supplier_name
        supplier.supplier_type = "Company"
        supplier.tax_id = format_cnpj(cnpj)

        # Set supplier group if configured
        if self.settings.supplier_group:
            supplier.supplier_group = self.settings.supplier_group

        # Add custom fields
        if hasattr(supplier, "inscricao_estadual"):
            supplier.inscricao_estadual = nf_doc.emitente_ie

        if hasattr(supplier, "inscricao_municipal"):
            supplier.inscricao_municipal = nf_doc.emitente_im

        supplier.insert(ignore_permissions=True)

        return supplier.name
