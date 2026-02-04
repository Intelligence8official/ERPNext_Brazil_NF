"""
Purchase Order matching service.
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate


class POMatcher:
    """
    Matches Nota Fiscal documents with Purchase Orders.
    """

    def __init__(self):
        self.settings = frappe.get_single("Nota Fiscal Settings")

    def auto_link_po(self, nf_doc):
        """
        Automatically find and link the best matching Purchase Order.

        Scoring algorithm:
        1. Filter POs by: supplier, date range, status
        2. Score each PO by item matches and value proximity
        3. Link if score exceeds threshold

        Returns:
            tuple: (po_name, status, message)
        """
        if not nf_doc.supplier:
            return None, "Not Applicable", _("No supplier linked")

        # Get date range
        date_range_days = self.settings.po_match_date_range_days or 30
        nf_date = getdate(nf_doc.data_emissao)

        start_date = add_days(nf_date, -date_range_days)
        end_date = add_days(nf_date, date_range_days)

        # Find candidate POs
        candidates = frappe.get_all(
            "Purchase Order",
            filters={
                "supplier": nf_doc.supplier,
                "transaction_date": ["between", [start_date, end_date]],
                "docstatus": 1,  # Submitted
                "status": ["in", ["To Receive and Bill", "To Receive", "To Bill"]]
            },
            fields=["name", "grand_total", "transaction_date"]
        )

        if not candidates:
            return None, "Not Found", _("No matching Purchase Orders found")

        # Score each candidate
        best_match = None
        best_score = 0

        tolerance = (self.settings.po_match_tolerance_percent or 5) / 100

        for po_data in candidates:
            score = self._calculate_match_score(nf_doc, po_data, tolerance)

            if score > best_score:
                best_score = score
                best_match = po_data

        # Minimum threshold to accept match
        if best_score >= 50:  # 50% confidence threshold
            return best_match["name"], "Linked", _("Matched with score {0}%").format(best_score)
        elif best_score >= 30:
            return best_match["name"], "Partial Match", _("Partial match with score {0}%").format(best_score)
        else:
            return None, "Not Found", _("No confident match found")

    def _calculate_match_score(self, nf_doc, po_data, tolerance):
        """
        Calculate match score between NF and PO.

        Scoring:
        - Value match (within tolerance): 30 points
        - Item count match: 20 points
        - Specific item matches: up to 40 points
        - Date proximity: 10 points

        Returns:
            int: Score from 0 to 100
        """
        score = 0

        # Value comparison (30 points max)
        if nf_doc.valor_total and po_data["grand_total"]:
            nf_value = float(nf_doc.valor_total)
            po_value = float(po_data["grand_total"])

            if po_value > 0:
                diff_pct = abs(nf_value - po_value) / po_value

                if diff_pct <= tolerance:
                    score += 30
                elif diff_pct <= tolerance * 2:
                    score += 15

        # Load PO for detailed comparison
        po_doc = frappe.get_doc("Purchase Order", po_data["name"])

        # Item count comparison (20 points max)
        nf_item_count = len(nf_doc.items)
        po_item_count = len(po_doc.items)

        if nf_item_count == po_item_count:
            score += 20
        elif abs(nf_item_count - po_item_count) <= 2:
            score += 10

        # Item matches (40 points max)
        item_match_score = self._calculate_item_match_score(nf_doc, po_doc)
        score += item_match_score

        # Date proximity (10 points max)
        nf_date = getdate(nf_doc.data_emissao)
        po_date = getdate(po_data["transaction_date"])
        days_diff = abs((nf_date - po_date).days)

        if days_diff <= 7:
            score += 10
        elif days_diff <= 14:
            score += 5

        return min(score, 100)

    def _calculate_item_match_score(self, nf_doc, po_doc):
        """
        Calculate score based on item matches.

        Returns:
            int: Score from 0 to 40
        """
        if not nf_doc.items or not po_doc.items:
            return 0

        matches = 0
        total_items = len(nf_doc.items)

        for nf_item in nf_doc.items:
            if not nf_item.item:
                continue

            for po_item in po_doc.items:
                if po_item.item_code == nf_item.item:
                    matches += 1
                    break

        if total_items > 0:
            return int((matches / total_items) * 40)

        return 0

    def get_suggested_pos(self, nf_doc, limit=5):
        """
        Get list of suggested Purchase Orders for manual linking.

        Returns:
            list: List of PO suggestions with scores
        """
        if not nf_doc.supplier:
            return []

        date_range_days = self.settings.po_match_date_range_days or 30
        nf_date = getdate(nf_doc.data_emissao) if nf_doc.data_emissao else frappe.utils.today()

        start_date = add_days(nf_date, -date_range_days)
        end_date = add_days(nf_date, date_range_days)

        candidates = frappe.get_all(
            "Purchase Order",
            filters={
                "supplier": nf_doc.supplier,
                "transaction_date": ["between", [start_date, end_date]],
                "docstatus": 1
            },
            fields=["name", "grand_total", "transaction_date", "status"]
        )

        tolerance = (self.settings.po_match_tolerance_percent or 5) / 100
        suggestions = []

        for po_data in candidates:
            score = self._calculate_match_score(nf_doc, po_data, tolerance)
            suggestions.append({
                "name": po_data["name"],
                "grand_total": po_data["grand_total"],
                "transaction_date": po_data["transaction_date"],
                "status": po_data["status"],
                "match_score": score
            })

        # Sort by score descending
        suggestions.sort(key=lambda x: x["match_score"], reverse=True)

        return suggestions[:limit]
