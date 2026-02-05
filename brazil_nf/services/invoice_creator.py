"""
Purchase Invoice creation service.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days


class InvoiceCreator:
    """
    Creates Purchase Invoices from Nota Fiscal documents.
    """

    def __init__(self):
        self.settings = frappe.get_single("Nota Fiscal Settings")

    def find_existing_invoice(self, nf_doc):
        """
        Find an existing Purchase Invoice that might match this NF.

        For Brazilian NF (NF-e, CT-e, NFS-e):
            1. Chave de acesso (exact match)
            2. Bill number + supplier (exact match)
            3. Supplier + value + date range (fuzzy match)

        For International Invoice:
            1. Invoice number + supplier (exact match)
            2. Supplier + value + date range (fuzzy match)

        Returns:
            str: Purchase Invoice name or None
        """
        # Handle international invoices differently
        if nf_doc.document_type == "Invoice":
            return self._find_existing_invoice_for_intl(nf_doc)

        # Brazilian NF processing
        # 1. Check by chave_de_acesso in custom field
        if nf_doc.chave_de_acesso:
            existing = frappe.db.get_value(
                "Purchase Invoice",
                {"chave_de_acesso": nf_doc.chave_de_acesso, "docstatus": ["<", 2]},
                "name"
            )
            if existing:
                return existing

        # 2. Check by bill_no (NF number) + supplier
        if nf_doc.numero and nf_doc.supplier:
            existing = frappe.db.get_value(
                "Purchase Invoice",
                {
                    "bill_no": nf_doc.numero,
                    "supplier": nf_doc.supplier,
                    "docstatus": ["<", 2]
                },
                "name"
            )
            if existing:
                return existing

        # 3. Fuzzy match: supplier + similar value + date range
        if nf_doc.supplier and nf_doc.valor_total and nf_doc.data_emissao:
            # Search within 5 days of issue date
            date_from = add_days(nf_doc.data_emissao, -5)
            date_to = add_days(nf_doc.data_emissao, 5)

            # Value tolerance: 1% or R$1, whichever is greater
            value_tolerance = max(flt(nf_doc.valor_total) * 0.01, 1)
            min_value = flt(nf_doc.valor_total) - value_tolerance
            max_value = flt(nf_doc.valor_total) + value_tolerance

            candidates = frappe.db.sql("""
                SELECT name, grand_total, posting_date, bill_no
                FROM `tabPurchase Invoice`
                WHERE supplier = %(supplier)s
                AND docstatus < 2
                AND posting_date BETWEEN %(date_from)s AND %(date_to)s
                AND grand_total BETWEEN %(min_value)s AND %(max_value)s
                AND (nota_fiscal IS NULL OR nota_fiscal = '')
                ORDER BY ABS(grand_total - %(value)s) ASC
                LIMIT 5
            """, {
                "supplier": nf_doc.supplier,
                "date_from": date_from,
                "date_to": date_to,
                "min_value": min_value,
                "max_value": max_value,
                "value": nf_doc.valor_total
            }, as_dict=True)

            if candidates:
                # Return the closest match
                return candidates[0].name

        return None

    def _find_existing_invoice_for_intl(self, nf_doc):
        """
        Find existing Purchase Invoice for international invoice.

        Args:
            nf_doc: Nota Fiscal document (Invoice type)

        Returns:
            str: Purchase Invoice name or None
        """
        # 1. Check by bill_no (invoice number) + supplier
        if nf_doc.invoice_number and nf_doc.supplier:
            existing = frappe.db.get_value(
                "Purchase Invoice",
                {
                    "bill_no": nf_doc.invoice_number,
                    "supplier": nf_doc.supplier,
                    "docstatus": ["<", 2]
                },
                "name"
            )
            if existing:
                return existing

        # 2. Fuzzy match: supplier + similar value + date range
        if nf_doc.supplier and nf_doc.valor_total and nf_doc.data_emissao:
            date_from = add_days(nf_doc.data_emissao, -5)
            date_to = add_days(nf_doc.data_emissao, 5)

            # Value tolerance for international (may have exchange rate variations)
            value_tolerance = max(flt(nf_doc.valor_total) * 0.05, 5)
            min_value = flt(nf_doc.valor_total) - value_tolerance
            max_value = flt(nf_doc.valor_total) + value_tolerance

            candidates = frappe.db.sql("""
                SELECT name, grand_total, posting_date, bill_no
                FROM `tabPurchase Invoice`
                WHERE supplier = %(supplier)s
                AND docstatus < 2
                AND posting_date BETWEEN %(date_from)s AND %(date_to)s
                AND grand_total BETWEEN %(min_value)s AND %(max_value)s
                AND (nota_fiscal IS NULL OR nota_fiscal = '')
                ORDER BY ABS(grand_total - %(value)s) ASC
                LIMIT 5
            """, {
                "supplier": nf_doc.supplier,
                "date_from": date_from,
                "date_to": date_to,
                "min_value": min_value,
                "max_value": max_value,
                "value": nf_doc.valor_total
            }, as_dict=True)

            if candidates:
                return candidates[0].name

        return None

    def link_existing_invoice(self, nf_doc, invoice_name):
        """
        Link an existing Purchase Invoice to this NF.

        Args:
            nf_doc: Nota Fiscal document
            invoice_name: Name of existing Purchase Invoice

        Returns:
            str: Invoice name
        """
        # Update the Purchase Invoice with NF reference
        frappe.db.set_value(
            "Purchase Invoice",
            invoice_name,
            {
                "nota_fiscal": nf_doc.name,
                "chave_de_acesso": nf_doc.chave_de_acesso
            },
            update_modified=True
        )

        # Update the NF document
        nf_doc.purchase_invoice = invoice_name
        nf_doc.invoice_status = "Linked"

        return invoice_name

    def create_purchase_invoice(self, nf_doc, submit=False, check_existing=True):
        """
        Create a Purchase Invoice from a Nota Fiscal.

        Args:
            nf_doc: Nota Fiscal document
            submit: Whether to submit the invoice
            check_existing: Whether to check for existing invoice first

        Returns:
            str: Created or linked invoice name
        """
        if not nf_doc.supplier:
            frappe.throw(_("Cannot create invoice without a linked supplier"))

        # Check for existing invoice first
        if check_existing:
            existing_invoice = self.find_existing_invoice(nf_doc)
            if existing_invoice:
                frappe.msgprint(
                    _("Found existing Purchase Invoice {0} that matches this NF. Linking instead of creating new.").format(existing_invoice),
                    indicator="blue",
                    alert=True
                )
                return self.link_existing_invoice(nf_doc, existing_invoice)

        # Create invoice
        invoice = frappe.new_doc("Purchase Invoice")
        invoice.supplier = nf_doc.supplier
        invoice.company = nf_doc.company

        # Handle international invoices differently
        if nf_doc.document_type == "Invoice":
            return self._create_invoice_from_intl(invoice, nf_doc, submit)

        # Brazilian NF processing
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

    def _create_invoice_from_intl(self, invoice, nf_doc, submit=False):
        """
        Create Purchase Invoice from international invoice.

        Args:
            invoice: Purchase Invoice document (new)
            nf_doc: Nota Fiscal document (Invoice type)
            submit: Whether to submit

        Returns:
            str: Invoice name
        """
        # Set dates
        invoice.posting_date = nf_doc.data_emissao or frappe.utils.today()
        invoice.bill_no = nf_doc.invoice_number
        invoice.bill_date = nf_doc.data_emissao

        # Set currency if different from company currency
        if nf_doc.currency and nf_doc.currency != "BRL":
            invoice.currency = nf_doc.currency
            if nf_doc.exchange_rate:
                invoice.conversion_rate = nf_doc.exchange_rate

        # Set custom fields
        if hasattr(invoice, "nota_fiscal"):
            invoice.nota_fiscal = nf_doc.name

        # Add single service item for international invoice
        self._add_intl_invoice_item(invoice, nf_doc)

        invoice.insert(ignore_permissions=True)

        # Update NF document
        nf_doc.purchase_invoice = invoice.name
        nf_doc.invoice_status = "Created"

        if submit:
            invoice.submit()
            nf_doc.invoice_status = "Submitted"

        nf_doc.save(ignore_permissions=True)

        return invoice.name

    def _add_intl_invoice_item(self, invoice, nf_doc):
        """
        Add item for international invoice.

        International invoices typically have one service line item.
        """
        from brazil_nf.services.item_manager import get_or_create_service_item

        # Try to get or create a service item
        service_item = get_or_create_service_item(nf_doc, self.settings)

        if service_item:
            description = nf_doc.invoice_description or f"{nf_doc.vendor_name} - Invoice #{nf_doc.invoice_number}"

            # Add billing period to description if available
            if nf_doc.billing_period_start and nf_doc.billing_period_end:
                description += f" ({nf_doc.billing_period_start} to {nf_doc.billing_period_end})"

            invoice.append("items", {
                "item_code": service_item,
                "item_name": nf_doc.invoice_description or f"Invoice {nf_doc.invoice_number}",
                "description": description,
                "qty": 1,
                "rate": nf_doc.valor_original_currency or nf_doc.valor_total or 0,
                "uom": "Unit"
            })
        else:
            frappe.throw(
                _("Cannot create Purchase Invoice: No service item could be created. "
                  "Please enable 'Auto-Create Items' in Nota Fiscal Settings."),
                title=_("Item Required")
            )

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
