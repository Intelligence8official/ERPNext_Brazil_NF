"""
Main NF processing pipeline.

Orchestrates the full processing flow for Nota Fiscal documents.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime


class NFProcessor:
    """
    Orchestrates the full NF processing pipeline.
    """

    def __init__(self):
        self.settings = frappe.get_single("Nota Fiscal Settings")

    def process(self, nf_doc):
        """
        Run full processing pipeline on a Nota Fiscal.

        Steps:
        1. Parse XML (if not already parsed)
        2. Process Supplier
        3. Process Items
        4. Match Purchase Order
        5. Optionally create Purchase Invoice
        """
        result = {
            "processing_status": "New",
            "supplier_status": nf_doc.supplier_status,
            "item_status": nf_doc.item_creation_status,
            "po_status": nf_doc.po_status
        }

        # Check if document is cancelled - cannot process cancelled documents
        if nf_doc.cancelada or nf_doc.processing_status == "Cancelled":
            frappe.throw(
                _("Cannot process a cancelled document. This Nota Fiscal was cancelled at SEFAZ."),
                title=_("Document Cancelled")
            )

        try:
            # Step 1: Ensure parsed
            if nf_doc.processing_status == "New":
                nf_doc.processing_status = "Parsed"

            # Step 2: Process Supplier
            nf_doc.processing_status = "Supplier Processing"
            nf_doc.save()

            supplier_result = self._process_supplier(nf_doc)
            result["supplier_status"] = supplier_result["status"]

            # Step 3: Process Items
            nf_doc.processing_status = "Item Processing"
            nf_doc.save()

            item_result = self._process_items(nf_doc)
            result["item_status"] = item_result["status"]

            # Step 4: Match PO
            if self.settings.enable_po_matching and nf_doc.supplier:
                nf_doc.processing_status = "PO Matching"
                nf_doc.save()

                po_result = self._match_po(nf_doc)
                result["po_status"] = po_result["status"]

            # Step 5: Create Invoice (if configured)
            if (self.settings.auto_create_invoice and
                    nf_doc.supplier and
                    nf_doc.item_creation_status == "All Created"):

                nf_doc.processing_status = "Invoice Creation"
                nf_doc.save()

                self._create_invoice(nf_doc)

            # Mark completed
            nf_doc.processing_status = "Completed"
            nf_doc.save()

            result["processing_status"] = "Completed"

        except Exception as e:
            nf_doc.processing_status = "Error"
            nf_doc.processing_error = str(e)
            nf_doc.save()

            result["processing_status"] = "Error"
            frappe.log_error(str(e), f"NF Processing Error: {nf_doc.name}")

        return result

    def _process_supplier(self, nf_doc):
        """Process supplier creation/linking."""
        from brazil_nf.services.supplier_manager import SupplierManager

        manager = SupplierManager()
        supplier, status, message = manager.process_nf_supplier(nf_doc)

        nf_doc.supplier = supplier
        nf_doc.supplier_status = status

        return {"status": status, "supplier": supplier, "message": message}

    def _process_items(self, nf_doc):
        """Process item creation/linking."""
        from brazil_nf.services.item_manager import ItemManager

        manager = ItemManager()
        created, total, status = manager.process_nf_items(nf_doc)

        nf_doc.item_creation_status = status

        return {"status": status, "created": created, "total": total}

    def _match_po(self, nf_doc):
        """Match and link Purchase Order."""
        from brazil_nf.services.po_matcher import POMatcher

        matcher = POMatcher()
        po_name, status, message = matcher.auto_link_po(nf_doc)

        nf_doc.purchase_order = po_name
        nf_doc.po_status = status

        return {"status": status, "po_name": po_name, "message": message}

    def _create_invoice(self, nf_doc):
        """Create or link Purchase Invoice."""
        from brazil_nf.services.invoice_creator import InvoiceCreator

        creator = InvoiceCreator()

        # First check if there's an existing invoice that matches
        existing = creator.find_existing_invoice(nf_doc)
        if existing:
            creator.link_existing_invoice(nf_doc, existing)
            frappe.logger().info(f"Linked existing Purchase Invoice {existing} to NF {nf_doc.name}")
            return {"invoice": existing, "linked": True}

        # Create new invoice
        submit = self.settings.invoice_submit_mode == "Auto Submit"
        pi_name = creator.create_purchase_invoice(nf_doc, submit=submit, check_existing=False)
        return {"invoice": pi_name, "linked": False}


def process_new_nf(doc, method=None):
    """
    Hook called after a new Nota Fiscal is inserted.

    Triggers automatic processing if enabled.
    """
    settings = frappe.get_single("Nota Fiscal Settings")

    if not settings.enabled:
        return

    # Queue processing as a background job
    frappe.enqueue(
        "brazil_nf.services.processor.process_nota_fiscal_background",
        nf_name=doc.name,
        queue="short"
    )


def validate_nf(doc, method=None):
    """
    Hook called when validating a Nota Fiscal.
    """
    # Validation is handled in the DocType controller
    pass


def process_nota_fiscal_background(nf_name):
    """
    Background job to process a Nota Fiscal.
    """
    nf_doc = frappe.get_doc("Nota Fiscal", nf_name)

    # Skip if document is cancelled
    if nf_doc.cancelada or nf_doc.processing_status == "Cancelled":
        frappe.logger().info(f"Skipping processing of cancelled NF: {nf_name}")
        return

    processor = NFProcessor()
    processor.process(nf_doc)


def cleanup_old_logs():
    """
    Daily job to clean up old import logs.
    """
    from brazil_nf.brazil_nf.doctype.nf_import_log.nf_import_log import cleanup_old_logs as cleanup

    deleted = cleanup(days=30)
    frappe.logger().info(f"Cleaned up {deleted} old NF Import Logs")


def cleanup_processed_xmls():
    """
    Weekly job to clean up processed XML files.
    """
    # TODO: Implement XML cleanup logic
    pass
