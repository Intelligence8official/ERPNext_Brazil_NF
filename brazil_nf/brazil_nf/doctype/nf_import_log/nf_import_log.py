# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class NFImportLog(Document):
    def before_insert(self):
        """Set default values."""
        if not self.started_at:
            self.started_at = now_datetime()

    def mark_completed(self, status="Success"):
        """Mark log as completed."""
        self.status = status
        self.completed_at = now_datetime()
        self.save(ignore_permissions=True)

    def mark_failed(self, error_message):
        """Mark log as failed with error."""
        self.status = "Failed"
        self.error_message = error_message
        self.completed_at = now_datetime()
        self.save(ignore_permissions=True)

    def update_counts(self, fetched=0, created=0, skipped=0, failed=0):
        """Update document counts."""
        self.documents_fetched = (self.documents_fetched or 0) + fetched
        self.documents_created = (self.documents_created or 0) + created
        self.documents_skipped = (self.documents_skipped or 0) + skipped
        self.documents_failed = (self.documents_failed or 0) + failed
        self.save(ignore_permissions=True)

    def update_nsu_range(self, nsu):
        """Update NSU range."""
        if not self.first_nsu:
            self.first_nsu = str(nsu)

        self.last_nsu = str(nsu)
        self.save(ignore_permissions=True)


def create_import_log(company, document_type, source):
    """Create a new import log entry."""
    log = frappe.new_doc("NF Import Log")
    log.company = company
    log.document_type = document_type
    log.source = source
    log.status = "Running"
    log.started_at = now_datetime()
    log.insert(ignore_permissions=True)

    return log


def get_recent_logs(company=None, limit=10):
    """Get recent import logs."""
    filters = {}
    if company:
        filters["company"] = company

    return frappe.get_all(
        "NF Import Log",
        filters=filters,
        fields=[
            "name", "company", "document_type", "source",
            "status", "started_at", "completed_at",
            "documents_fetched", "documents_created",
            "documents_skipped", "documents_failed"
        ],
        order_by="creation desc",
        limit=limit
    )


def cleanup_old_logs(days=30):
    """Delete logs older than specified days."""
    from frappe.utils import add_days, now_datetime

    cutoff = add_days(now_datetime(), -days)

    old_logs = frappe.get_all(
        "NF Import Log",
        filters={"creation": ["<", cutoff]},
        pluck="name"
    )

    for log_name in old_logs:
        frappe.delete_doc("NF Import Log", log_name, ignore_permissions=True)

    frappe.db.commit()

    return len(old_logs)
