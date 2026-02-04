# Copyright (c) 2024, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class NFCompanySettings(Document):
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
        if self.certificate_file and self.certificate_password:
            try:
                from brazil_nf.services.cert_utils import validate_pfx_certificate

                expiry = validate_pfx_certificate(
                    self.certificate_file,
                    self.certificate_password
                )

                self.certificate_expiry = expiry
                self.certificate_valid = 1

            except Exception as e:
                self.certificate_valid = 0
                frappe.msgprint(
                    _("Certificate validation failed: {0}").format(str(e)),
                    indicator="red",
                    alert=True
                )
        else:
            self.certificate_valid = 0

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
