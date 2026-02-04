# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class NotaFiscal(Document):
    def before_insert(self):
        """Set default values before insert."""
        if not self.data_recebimento:
            self.data_recebimento = now_datetime()

        if not self.processing_status:
            self.processing_status = "New"

    def validate(self):
        """Validate document before save."""
        self.validate_chave_de_acesso()
        self.validate_cnpj()

    def validate_chave_de_acesso(self):
        """Validate the access key format and check digit."""
        if not self.chave_de_acesso:
            return

        from brazil_nf.utils.chave_acesso import validate_chave_acesso

        if not validate_chave_acesso(self.chave_de_acesso):
            frappe.throw(
                _("Invalid Chave de Acesso. Please check the 44-digit access key."),
                title=_("Validation Error")
            )

    def validate_cnpj(self):
        """Validate CNPJ format."""
        if not self.emitente_cnpj:
            return

        from brazil_nf.utils.cnpj import validate_cnpj, clean_cnpj

        cleaned = clean_cnpj(self.emitente_cnpj)
        if len(cleaned) == 14 and not validate_cnpj(cleaned):
            frappe.msgprint(
                _("Warning: Emitente CNPJ may be invalid."),
                indicator="orange",
                alert=True
            )

    def on_update(self):
        """Actions after document is updated."""
        # Update linked Purchase Invoice if exists
        if self.purchase_invoice:
            frappe.db.set_value(
                "Purchase Invoice",
                self.purchase_invoice,
                "chave_de_acesso",
                self.chave_de_acesso
            )

    def get_indicator_color(self, status_field):
        """Get indicator color for status fields."""
        colors = {
            # Processing Status
            "New": "gray",
            "Parsed": "blue",
            "Supplier Processing": "blue",
            "Item Processing": "blue",
            "PO Matching": "blue",
            "Invoice Creation": "blue",
            "Completed": "green",
            "Error": "red",
            # Supplier Status
            "Pending": "gray",
            "Linked": "green",
            "Created": "blue",
            "Failed": "red",
            "Not Found": "orange",
            # Item Creation Status
            "All Created": "green",
            "Partial": "yellow",
            # PO Status
            "Partial Match": "yellow",
            "Not Applicable": "gray",
            # Invoice Status
            "Submitted": "green"
        }

        status = getattr(self, status_field, "")
        return colors.get(status, "gray")

    @frappe.whitelist()
    def process_document(self):
        """Manually trigger processing of this document."""
        from brazil_nf.services.processor import NFProcessor

        processor = NFProcessor()
        result = processor.process(self)

        return result

    @frappe.whitelist()
    def create_supplier(self):
        """Manually create supplier from this document."""
        from brazil_nf.services.supplier_manager import SupplierManager

        manager = SupplierManager()
        supplier, status, message = manager.process_nf_supplier(self)

        self.supplier = supplier
        self.supplier_status = status
        self.save()

        return {"supplier": supplier, "status": status, "message": message}

    @frappe.whitelist()
    def create_items(self):
        """Manually create items from this document."""
        from brazil_nf.services.item_manager import ItemManager

        manager = ItemManager()
        created, total, status = manager.process_nf_items(self)

        self.item_creation_status = status
        self.save()

        return {"created": created, "total": total, "status": status}

    @frappe.whitelist()
    def match_purchase_order(self):
        """Manually match with Purchase Order."""
        from brazil_nf.services.po_matcher import POMatcher

        matcher = POMatcher()
        po_name, status, message = matcher.auto_link_po(self)

        self.purchase_order = po_name
        self.po_status = status
        self.save()

        return {"purchase_order": po_name, "status": status, "message": message}

    @frappe.whitelist()
    def create_purchase_invoice(self, submit=False):
        """Create Purchase Invoice from this document."""
        from brazil_nf.services.invoice_creator import InvoiceCreator

        creator = InvoiceCreator()
        invoice_name = creator.create_purchase_invoice(self, submit=submit)

        self.purchase_invoice = invoice_name
        self.invoice_status = "Submitted" if submit else "Created"
        self.save()

        return {"invoice": invoice_name}

    @frappe.whitelist()
    def parse_xml(self):
        """Parse the XML content and populate fields."""
        if not self.xml_content:
            frappe.throw(_("No XML content to parse"))

        from brazil_nf.services.xml_parser import NFXMLParser

        parser = NFXMLParser()
        data = parser.parse(self.xml_content)

        # Update fields from parsed data
        for field, value in data.items():
            if hasattr(self, field) and value is not None:
                setattr(self, field, value)

        self.processing_status = "Parsed"
        self.save()

        return {"status": "success", "fields_updated": len(data)}


def get_list_context(context=None):
    """Configure list view."""
    return {
        "title": _("Nota Fiscal"),
        "get_list": get_nota_fiscal_list,
        "no_breadcrumbs": False,
    }


def get_nota_fiscal_list(doctype, txt, filters, limit_start, limit_page_length=20, order_by="creation desc"):
    """Get list of Nota Fiscal documents."""
    return frappe.db.sql(
        """
        SELECT
            name, document_type, chave_de_acesso, numero, data_emissao,
            emitente_cnpj, emitente_razao_social, valor_total,
            processing_status, supplier_status, item_creation_status, po_status
        FROM `tabNota Fiscal`
        WHERE %(txt_condition)s
        ORDER BY %(order_by)s
        LIMIT %(limit_start)s, %(limit_page_length)s
        """,
        {
            "txt_condition": "1=1" if not txt else f"emitente_razao_social LIKE '%{txt}%'",
            "order_by": order_by,
            "limit_start": limit_start,
            "limit_page_length": limit_page_length
        },
        as_dict=True
    )
