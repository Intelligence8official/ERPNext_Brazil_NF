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
        2. Search by NCM + description similarity
        3. If found: link to existing item
        4. If not found and auto_create enabled: create item

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
        # Search in Item Supplier table by supplier item code
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

        # Search by NCM code
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

        return None

    def _description_matches(self, item_name, nf_description):
        """
        Check if item name loosely matches NF description.
        """
        if not item_name or not nf_description:
            return False

        # Simple word matching
        item_words = set(item_name.lower().split())
        nf_words = set(nf_description.lower().split())

        # At least 50% of words should match
        common = item_words.intersection(nf_words)
        return len(common) >= min(len(item_words), len(nf_words)) * 0.5

    def create_item(self, nf_item, nf_doc):
        """
        Create a new item from Nota Fiscal item data.

        Args:
            nf_item: Nota Fiscal Item
            nf_doc: Nota Fiscal document

        Returns:
            str: Created item code
        """
        item_name = nf_item.descricao or f"Item {nf_item.codigo_produto}"

        item = frappe.new_doc("Item")
        item.item_code = nf_item.codigo_produto or item_name[:140]
        item.item_name = item_name[:140]
        item.description = nf_item.descricao

        # Set item group if configured
        if self.settings.item_group:
            item.item_group = self.settings.item_group
        else:
            item.item_group = "All Item Groups"

        # Set custom fields
        if hasattr(item, "ncm_code"):
            item.ncm_code = nf_item.ncm

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
