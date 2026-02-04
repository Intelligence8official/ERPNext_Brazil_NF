# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class NotaFiscalSettings(Document):
    def validate(self):
        """Validate settings."""
        self.validate_fetch_interval()
        self.validate_email_settings()

    def validate_fetch_interval(self):
        """Ensure fetch interval is reasonable."""
        if self.fetch_interval_minutes and self.fetch_interval_minutes < 5:
            frappe.throw(
                _("Fetch interval must be at least 5 minutes to avoid API rate limits"),
                title=_("Validation Error")
            )

    def validate_email_settings(self):
        """Validate email configuration."""
        if self.email_import_enabled and not self.email_account:
            frappe.throw(
                _("Please select an Email Account when Email Import is enabled"),
                title=_("Validation Error")
            )


def get_settings():
    """Get Nota Fiscal Settings singleton."""
    return frappe.get_single("Nota Fiscal Settings")


def is_enabled():
    """Check if module is enabled."""
    settings = get_settings()
    return settings.enabled


def get_sefaz_environment():
    """Get current SEFAZ environment."""
    settings = get_settings()
    return settings.sefaz_environment or "Production"


def should_auto_create_supplier():
    """Check if auto-creation of suppliers is enabled."""
    settings = get_settings()
    return settings.auto_create_supplier


def should_auto_create_item():
    """Check if auto-creation of items is enabled."""
    settings = get_settings()
    return settings.auto_create_item


def should_auto_create_invoice():
    """Check if auto-creation of invoices is enabled."""
    settings = get_settings()
    return settings.auto_create_invoice


def get_default_supplier_group():
    """Get default supplier group for auto-created suppliers."""
    settings = get_settings()
    return settings.supplier_group


def get_default_item_group():
    """Get default item group for auto-created items."""
    settings = get_settings()
    return settings.item_group
