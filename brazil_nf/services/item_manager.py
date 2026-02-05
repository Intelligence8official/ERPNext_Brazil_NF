"""
Item management service for auto-creation and linking.
"""

import frappe
from frappe import _


class ItemManager:
    """
    Manages item creation and linking for Nota Fiscal documents.
    """

    def __init__(self):
        self.settings = frappe.get_single("Nota Fiscal Settings")

    def process_nf_items(self, nf_doc):
        """
        Process items for a Nota Fiscal.

        For each item:
        1. Search by supplier item code
        2. Search by NCM/service code
        3. Search in past invoices from same supplier
        4. If found: link to existing item
        5. If not found and auto_create enabled: create item

        Returns:
            tuple: (items_created, total_items, status)
        """
        total = len(nf_doc.items)
        created = 0
        linked = 0
        failed = 0

        for nf_item in nf_doc.items:
            try:
                item_code, status = self.process_single_item(nf_item, nf_doc)
                nf_item.item = item_code
                nf_item.item_status = status

                if status == "Created":
                    created += 1
                elif status == "Linked":
                    linked += 1
                else:
                    failed += 1

            except Exception as e:
                frappe.log_error(str(e), f"Item Processing Error: {nf_item.codigo_produto}")
                nf_item.item_status = "Failed"
                failed += 1

        # Determine overall status
        if failed == 0:
            status = "All Created"
        elif failed == total:
            status = "Failed"
        else:
            status = "Partial"

        return created + linked, total, status

    def process_single_item(self, nf_item, nf_doc):
        """
        Process a single item.

        Returns:
            tuple: (item_code, status)
        """
        # Try to find existing item
        existing = self.find_item(nf_item, nf_doc)

        if existing:
            return existing, "Linked"

        # Auto-create if enabled
        if self.settings.auto_create_item:
            item_code = self.create_item(nf_item, nf_doc)
            return item_code, "Created"

        return None, "Failed"

    def find_item(self, nf_item, nf_doc):
        """
        Find an existing item by various criteria.

        Args:
            nf_item: Nota Fiscal Item
            nf_doc: Nota Fiscal document

        Returns:
            str: Item code or None
        """
        # 1. Search in Item Supplier table by supplier item code
        if nf_item.codigo_produto and nf_doc.supplier:
            item_supplier = frappe.get_all(
                "Item Supplier",
                filters={
                    "supplier": nf_doc.supplier,
                    "supplier_part_no": nf_item.codigo_produto
                },
                pluck="parent",
                limit=1
            )

            if item_supplier:
                return item_supplier[0]

        # 2. Search by service code (cTribNac) for NFS-e
        if nf_item.codigo_tributacao_nacional:
            items = frappe.get_all(
                "Item",
                filters={"custom_codigo_servico": nf_item.codigo_tributacao_nacional},
                pluck="name",
                limit=1
            )
            if items:
                return items[0]

        # 3. Search by NCM code for NF-e
        if nf_item.ncm:
            items = frappe.get_all(
                "Item",
                filters={"ncm_code": nf_item.ncm},
                pluck="name",
                limit=5
            )

            # If multiple matches, try to match by description
            if items and nf_item.descricao:
                for item_code in items:
                    item = frappe.get_doc("Item", item_code)
                    if self._description_matches(item.item_name, nf_item.descricao):
                        return item_code

            if len(items) == 1:
                return items[0]

        # 4. Search in past Purchase Invoices from same supplier
        if nf_doc.supplier:
            item_from_history = self._find_item_from_invoice_history(nf_item, nf_doc)
            if item_from_history:
                return item_from_history

        return None

    def _find_item_from_invoice_history(self, nf_item, nf_doc):
        """
        Find item from past invoices with the same supplier.

        Looks for:
        - Same supplier + similar value
        - Same supplier + similar description
        """
        # Get recent invoices from this supplier
        invoices = frappe.get_all(
            "Purchase Invoice",
            filters={
                "supplier": nf_doc.supplier,
                "docstatus": ["in", [0, 1]]  # Draft or Submitted
            },
            pluck="name",
            limit=10,
            order_by="creation desc"
        )

        if not invoices:
            return None

        # Check invoice items
        for inv_name in invoices:
            inv_items = frappe.get_all(
                "Purchase Invoice Item",
                filters={"parent": inv_name},
                fields=["item_code", "item_name", "rate", "description"]
            )

            for inv_item in inv_items:
                if not inv_item.item_code:
                    continue

                # Match by similar rate (within 5%)
                if nf_item.valor_total and inv_item.rate:
                    rate_diff = abs(float(nf_item.valor_total) - float(inv_item.rate))
                    rate_tolerance = float(inv_item.rate) * 0.05
                    if rate_diff <= rate_tolerance:
                        # Also check if description is similar
                        if self._description_matches(inv_item.item_name or inv_item.description, nf_item.descricao):
                            return inv_item.item_code

                # Match by description similarity
                if nf_item.descricao and self._description_matches(inv_item.item_name or inv_item.description, nf_item.descricao):
                    return inv_item.item_code

        return None

    def _description_matches(self, item_name, nf_description):
        """
        Check if item name loosely matches NF description.
        """
        if not item_name or not nf_description:
            return False

        # Normalize strings
        item_lower = item_name.lower().strip()
        nf_lower = nf_description.lower().strip()

        # Exact match
        if item_lower == nf_lower:
            return True

        # Simple word matching
        item_words = set(item_lower.split())
        nf_words = set(nf_lower.split())

        # Remove common stop words
        stop_words = {'de', 'da', 'do', 'das', 'dos', 'em', 'para', 'com', 'e', 'ou', 'a', 'o', 'as', 'os'}
        item_words = item_words - stop_words
        nf_words = nf_words - stop_words

        if not item_words or not nf_words:
            return False

        # At least 50% of words should match
        common = item_words.intersection(nf_words)
        min_words = min(len(item_words), len(nf_words))
        return len(common) >= min_words * 0.5

    def create_item(self, nf_item, nf_doc):
        """
        Create a new item from Nota Fiscal item data.

        Args:
            nf_item: Nota Fiscal Item
            nf_doc: Nota Fiscal document

        Returns:
            str: Created item code
        """
        is_service = nf_doc.document_type == "NFS-e"

        # Generate item code
        if nf_item.codigo_produto:
            item_code = nf_item.codigo_produto[:140]
        elif nf_item.codigo_tributacao_nacional:
            item_code = f"SERV-{nf_item.codigo_tributacao_nacional}"
        else:
            # Use a hash of description to create unique code
            import hashlib
            desc_hash = hashlib.md5((nf_item.descricao or "item").encode()).hexdigest()[:8]
            item_code = f"NF-{desc_hash.upper()}"

        # Check if this item_code already exists
        if frappe.db.exists("Item", item_code):
            return item_code

        # Generate item name from description
        item_name = nf_item.descricao or f"Item {item_code}"
        item_name = item_name[:140]

        item = frappe.new_doc("Item")
        item.item_code = item_code
        item.item_name = item_name
        item.description = nf_item.descricao

        # Set item group if configured
        if self.settings.item_group:
            item.item_group = self.settings.item_group
        else:
            # Try to find a services group for NFS-e
            if is_service:
                service_groups = frappe.get_all(
                    "Item Group",
                    filters={"name": ["like", "%servi%"]},
                    pluck="name",
                    limit=1
                )
                item.item_group = service_groups[0] if service_groups else "All Item Groups"
            else:
                item.item_group = "All Item Groups"

        # For services, mark as non-stock and set expense account
        if is_service:
            item.is_stock_item = 0
            item.include_item_in_manufacturing = 0

            # Get default expense account from company
            default_expense = frappe.db.get_value(
                "Company",
                nf_doc.company,
                "default_expense_account"
            )
            if default_expense:
                item.append("item_defaults", {
                    "company": nf_doc.company,
                    "expense_account": default_expense
                })

        # Set custom fields
        if hasattr(item, "ncm_code") and nf_item.ncm:
            item.ncm_code = nf_item.ncm

        if hasattr(item, "custom_codigo_servico") and nf_item.codigo_tributacao_nacional:
            item.custom_codigo_servico = nf_item.codigo_tributacao_nacional

        # Set stock UOM
        item.stock_uom = nf_item.unidade or "Unit"

        # Ensure the UOM exists
        if not frappe.db.exists("UOM", item.stock_uom):
            item.stock_uom = "Unit"

        item.insert(ignore_permissions=True)

        # Add to Item Supplier if we have supplier
        if nf_doc.supplier and nf_item.codigo_produto:
            item.append("supplier_items", {
                "supplier": nf_doc.supplier,
                "supplier_part_no": nf_item.codigo_produto
            })
            item.save(ignore_permissions=True)

        return item.name


def get_or_create_service_item(nf_doc, settings):
    """
    Get or create a service item for NFS-e invoices or international invoices.

    This is used when no specific item can be matched.

    Args:
        nf_doc: Nota Fiscal document
        settings: Nota Fiscal Settings

    Returns:
        str: Item code
    """
    # For international invoices, try to get/create vendor-specific service item
    if nf_doc.document_type == "Invoice":
        return _get_or_create_international_service_item(nf_doc, settings)

    # Look for a generic service item first
    generic_service = frappe.get_all(
        "Item",
        filters={
            "item_code": ["like", "%SERVICO%"],
            "is_stock_item": 0
        },
        pluck="name",
        limit=1
    )

    if generic_service:
        return generic_service[0]

    # Try to find from invoice history with same supplier
    if nf_doc.supplier:
        invoices = frappe.get_all(
            "Purchase Invoice",
            filters={
                "supplier": nf_doc.supplier,
                "docstatus": ["in", [0, 1]]
            },
            pluck="name",
            limit=5,
            order_by="creation desc"
        )

        for inv_name in invoices:
            items = frappe.get_all(
                "Purchase Invoice Item",
                filters={"parent": inv_name, "item_code": ["is", "set"]},
                pluck="item_code",
                limit=1
            )
            if items:
                return items[0]

    # Create generic service item if auto_create is enabled
    if settings.auto_create_item:
        item_code = "SERVICO-GENERICO"

        if frappe.db.exists("Item", item_code):
            return item_code

        item = frappe.new_doc("Item")
        item.item_code = item_code
        item.item_name = "Servico Generico"
        item.description = "Item generico para servicos (NFS-e)"
        item.is_stock_item = 0
        item.include_item_in_manufacturing = 0

        if settings.item_group:
            item.item_group = settings.item_group
        else:
            item.item_group = "All Item Groups"

        # Set default expense account
        default_expense = frappe.db.get_value(
            "Company",
            nf_doc.company,
            "default_expense_account"
        )
        if default_expense:
            item.append("item_defaults", {
                "company": nf_doc.company,
                "expense_account": default_expense
            })

        item.stock_uom = "Unit"
        item.insert(ignore_permissions=True)

        return item.name

    return None


def _get_or_create_international_service_item(nf_doc, settings):
    """
    Get or create a service item for international invoices.

    Creates vendor-specific service items like "GitHub Services", "AWS Services", etc.

    Args:
        nf_doc: Nota Fiscal document (Invoice type)
        settings: Nota Fiscal Settings

    Returns:
        str: Item code
    """
    vendor_name = nf_doc.vendor_name or "International"

    # Create a clean item code from vendor name
    import re
    vendor_slug = re.sub(r'[^a-zA-Z0-9]', '', vendor_name.upper())[:20]
    item_code = f"SVC-{vendor_slug}"

    # Check if already exists
    if frappe.db.exists("Item", item_code):
        return item_code

    # Try to find from invoice history with same supplier
    if nf_doc.supplier:
        invoices = frappe.get_all(
            "Purchase Invoice",
            filters={
                "supplier": nf_doc.supplier,
                "docstatus": ["in", [0, 1]]
            },
            pluck="name",
            limit=5,
            order_by="creation desc"
        )

        for inv_name in invoices:
            items = frappe.get_all(
                "Purchase Invoice Item",
                filters={"parent": inv_name, "item_code": ["is", "set"]},
                pluck="item_code",
                limit=1
            )
            if items:
                return items[0]

    # Create vendor-specific service item if auto_create is enabled
    if settings.auto_create_item:
        item = frappe.new_doc("Item")
        item.item_code = item_code
        item.item_name = f"{vendor_name} Services"
        item.description = f"Services from {vendor_name}"
        item.is_stock_item = 0
        item.include_item_in_manufacturing = 0

        if settings.item_group:
            item.item_group = settings.item_group
        else:
            # Try to find a services group
            service_groups = frappe.get_all(
                "Item Group",
                filters={"name": ["like", "%servi%"]},
                pluck="name",
                limit=1
            )
            item.item_group = service_groups[0] if service_groups else "All Item Groups"

        # Set default expense account
        if nf_doc.company:
            default_expense = frappe.db.get_value(
                "Company",
                nf_doc.company,
                "default_expense_account"
            )
            if default_expense:
                item.append("item_defaults", {
                    "company": nf_doc.company,
                    "expense_account": default_expense
                })

        item.stock_uom = "Unit"
        item.insert(ignore_permissions=True)

        # Add to Item Supplier if we have supplier
        if nf_doc.supplier:
            item.append("supplier_items", {
                "supplier": nf_doc.supplier,
                "supplier_part_no": item_code
            })
            item.save(ignore_permissions=True)

        return item.name

    return None
