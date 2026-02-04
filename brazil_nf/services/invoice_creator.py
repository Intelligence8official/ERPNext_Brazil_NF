"""
Purchase Invoice creation service.
"""

import frappe
from frappe import _


class InvoiceCreator:
    """
    Creates Purchase Invoices from Nota Fiscal documents.
    """

    def __init__(self):
        self.settings = frappe.get_single("Nota Fiscal Settings")

    def create_purchase_invoice(self, nf_doc, submit=False):
        """
        Create a Purchase Invoice from a Nota Fiscal.

        Args:
            nf_doc: Nota Fiscal document
            submit: Whether to submit the invoice

        Returns:
            str: Created invoice name
        """
        if not nf_doc.supplier:
            frappe.throw(_("Cannot create invoice without a linked supplier"))

        # Create invoice
        invoice = frappe.new_doc("Purchase Invoice")
        invoice.supplier = nf_doc.supplier
        invoice.company = nf_doc.company

        # Set dates
        invoice.posting_date = nf_doc.data_emissao or frappe.utils.today()
        invoice.bill_no = nf_doc.numero
        invoice.bill_date = nf_doc.data_emissao

        # Set custom fields
        if hasattr(invoice, "nota_fiscal"):
            invoice.nota_fiscal = nf_doc.name
        if hasattr(invoice, "chave_de_acesso"):
            invoice.chave_de_acesso = nf_doc.chave_de_acesso

        # Link to PO if exists
        if nf_doc.purchase_order:
            # Get items from PO
            self._add_items_from_po(invoice, nf_doc)
        else:
            # Add items from NF
            self._add_items_from_nf(invoice, nf_doc)

        # Set taxes
        self._add_taxes(invoice, nf_doc)

        invoice.insert(ignore_permissions=True)

        # Update NF document
        nf_doc.purchase_invoice = invoice.name
        nf_doc.invoice_status = "Created"

        if submit:
            invoice.submit()
            nf_doc.invoice_status = "Submitted"

        nf_doc.save(ignore_permissions=True)

        return invoice.name

    def _add_items_from_po(self, invoice, nf_doc):
        """
        Add items from linked Purchase Order.
        """
        po = frappe.get_doc("Purchase Order", nf_doc.purchase_order)

        for po_item in po.items:
            invoice.append("items", {
                "item_code": po_item.item_code,
                "item_name": po_item.item_name,
                "description": po_item.description,
                "qty": po_item.qty,
                "rate": po_item.rate,
                "amount": po_item.amount,
                "uom": po_item.uom,
                "purchase_order": nf_doc.purchase_order,
                "po_detail": po_item.name
            })

    def _add_items_from_nf(self, invoice, nf_doc):
        """
        Add items directly from Nota Fiscal.
        """
        for nf_item in nf_doc.items:
            if not nf_item.item:
                continue

            invoice.append("items", {
                "item_code": nf_item.item,
                "item_name": nf_item.descricao,
                "description": nf_item.descricao,
                "qty": nf_item.quantidade or 1,
                "rate": nf_item.valor_unitario or nf_item.valor_total,
                "uom": nf_item.unidade or "Unit"
            })

        # If no items with linked ERPNext items, try to find/create a service item
        if not invoice.items:
            from brazil_nf.services.item_manager import get_or_create_service_item

            service_item = get_or_create_service_item(nf_doc, self.settings)

            if service_item:
                invoice.append("items", {
                    "item_code": service_item,
                    "item_name": nf_doc.descricao_servico or f"Nota Fiscal {nf_doc.numero}",
                    "description": nf_doc.descricao_servico or f"NF {nf_doc.numero} - {nf_doc.emitente_razao_social or ''}".strip(),
                    "qty": 1,
                    "rate": nf_doc.valor_total or 0,
                    "uom": "Unit"
                })
            else:
                # Cannot create invoice without items
                frappe.throw(
                    _("Cannot create Purchase Invoice: No items could be linked or created. "
                      "Please enable 'Auto-Create Items' in Nota Fiscal Settings or manually link items."),
                    title=_("Item Required")
                )

    def _add_taxes(self, invoice, nf_doc):
        """
        Add tax entries based on NF values.

        Note: This is a simplified implementation.
        In production, you would need to configure proper tax templates
        based on the specific tax regime and document type.
        """
        # Tax handling would depend on your ERPNext tax configuration
        # This is a placeholder for the tax logic
        pass
