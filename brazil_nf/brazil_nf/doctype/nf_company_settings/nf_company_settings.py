# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password


class NFCompanySettings(Document):
    def get_certificate_password(self):
        """Get the decrypted certificate password."""
        if not self.name or self.is_new():
            # During creation, password is in plain text
            return self.certificate_password

        # For saved documents, decrypt the password
        return get_decrypted_password(
            "NF Company Settings",
            self.name,
            "certificate_password"
        )
    def validate(self):
        """Validate company settings."""
        self.validate_cnpj()
        self.validate_certificate()

    def validate_cnpj(self):
        """Validate CNPJ format."""
        if self.cnpj:
            from brazil_nf.utils.cnpj import validate_cnpj, clean_cnpj

            cleaned = clean_cnpj(self.cnpj)
            if len(cleaned) != 14:
                frappe.throw(
                    _("CNPJ must be 14 digits"),
                    title=_("Validation Error")
                )

            if not validate_cnpj(cleaned):
                frappe.msgprint(
                    _("Warning: CNPJ may be invalid. Please verify."),
                    indicator="orange",
                    alert=True
                )

            # Store cleaned version
            self.cnpj = cleaned

    def validate_certificate(self):
        """Validate the uploaded certificate."""
        # If no certificate file, clear all certificate-related fields
        if not self.certificate_file:
            self.certificate_valid = 0
            self.certificate_expiry = None
            self.certificate_password = ""
            return

        # If certificate file exists but no password, mark as invalid
        if not self.certificate_password:
            self.certificate_valid = 0
            self.certificate_expiry = None
            return

        # Try to validate the certificate
        try:
            from brazil_nf.services.cert_utils import validate_pfx_certificate

            expiry = validate_pfx_certificate(
                self.certificate_file,
                self.certificate_password
            )

            self.certificate_expiry = expiry
            self.certificate_valid = 1

            frappe.msgprint(
                _("Certificate validated successfully. Expires on {0}").format(expiry),
                indicator="green",
                alert=True
            )

        except Exception as e:
            self.certificate_valid = 0
            self.certificate_expiry = None
            frappe.msgprint(
                _("Certificate validation failed: {0}").format(str(e)),
                indicator="red",
                alert=True
            )

    @frappe.whitelist()
    def test_connection(self):
        """Test connection to SEFAZ using this company's certificate."""
        if not self.certificate_valid:
            frappe.throw(_("Certificate is not valid. Please upload a valid certificate."))

        try:
            from brazil_nf.services.dfe_client import test_sefaz_connection

            result = test_sefaz_connection(self.name)
            return result
        except Exception as e:
            frappe.throw(_("Connection test failed: {0}").format(str(e)))

    @frappe.whitelist()
    def fetch_now(self, document_type=None):
        """Manually trigger fetch for this company."""
        from brazil_nf.services.dfe_client import fetch_documents_for_company

        result = fetch_documents_for_company(self.name, document_type)
        self.last_sync = now_datetime()
        self.save()

        return result

    def update_last_nsu(self, document_type, nsu):
        """Update the last NSU for a document type."""
        field_map = {
            "NF-e": "last_nsu_nfe",
            "CT-e": "last_nsu_cte",
            "NFS-e": "last_nsu_nfse"
        }

        field = field_map.get(document_type)
        if field:
            setattr(self, field, str(nsu))
            self.last_sync = now_datetime()
            self.save(ignore_permissions=True)

    def get_last_nsu(self, document_type):
        """Get the last NSU for a document type."""
        field_map = {
            "NF-e": "last_nsu_nfe",
            "CT-e": "last_nsu_cte",
            "NFS-e": "last_nsu_nfse"
        }

        field = field_map.get(document_type)
        if field:
            return getattr(self, field, "0") or "0"

        return "0"


def get_company_settings(company):
    """Get NF Company Settings for a company."""
    if frappe.db.exists("NF Company Settings", company):
        return frappe.get_doc("NF Company Settings", company)
    return None


def get_all_enabled_companies():
    """Get all companies with sync enabled."""
    return frappe.get_all(
        "NF Company Settings",
        filters={"sync_enabled": 1, "certificate_valid": 1},
        fields=["name", "company", "cnpj"]
    )


@frappe.whitelist()
def test_connection(company_settings_name):
    """
    Test connection to SEFAZ using company's certificate.

    Args:
        company_settings_name: Name of NF Company Settings document

    Returns:
        dict: Test result with success flag and message
    """
    doc = frappe.get_doc("NF Company Settings", company_settings_name)

    if not doc.certificate_valid:
        return {
            "success": False,
            "message": _("Certificate is not valid. Please upload a valid certificate and save.")
        }

    if not doc.certificate_file:
        return {
            "success": False,
            "message": _("No certificate file uploaded.")
        }

    try:
        from brazil_nf.services.dfe_client import test_sefaz_connection
        result = test_sefaz_connection(company_settings_name)

        return {
            "success": result.get("status") == "success",
            "message": result.get("message", _("Connection test completed"))
        }
    except Exception as e:
        frappe.log_error(str(e), "SEFAZ Connection Test Error")
        return {
            "success": False,
            "message": _("Connection test failed: {0}").format(str(e))
        }


@frappe.whitelist()
def fetch_documents(company_settings_name, document_type=None):
    """
    Fetch documents from SEFAZ for a company.

    Args:
        company_settings_name: Name of NF Company Settings document
        document_type: Optional specific document type (NF-e, CT-e, NFS-e)

    Returns:
        dict: Fetch results
    """
    doc = frappe.get_doc("NF Company Settings", company_settings_name)

    if not doc.certificate_valid:
        frappe.throw(_("Certificate is not valid. Please upload a valid certificate."))

    try:
        from brazil_nf.services.dfe_client import fetch_documents_for_company

        result = fetch_documents_for_company(company_settings_name, document_type)

        # Update last sync time
        doc.last_sync = now_datetime()
        doc.save(ignore_permissions=True)

        return result
    except Exception as e:
        frappe.log_error(str(e), "SEFAZ Fetch Error")
        frappe.throw(_("Fetch failed: {0}").format(str(e)))
