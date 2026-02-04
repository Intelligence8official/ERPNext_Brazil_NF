"""
Email monitoring service for NF attachments.
"""

import frappe
from frappe import _


def check_emails():
    """
    Scheduled job to check emails for NF attachments.

    Uses Frappe's Email Account to monitor incoming emails
    and process XML attachments.
    """
    settings = frappe.get_single("Nota Fiscal Settings")

    if not settings.enabled or not settings.email_import_enabled:
        return

    if not settings.email_account:
        return

    # Get unprocessed communications from the configured email account
    communications = frappe.get_all(
        "Communication",
        filters={
            "email_account": settings.email_account,
            "communication_type": "Communication",
            "sent_or_received": "Received",
            "nf_processed": 0
        },
        fields=["name", "subject", "content"],
        order_by="creation desc",
        limit=50
    )

    for comm in communications:
        process_email(comm["name"], settings)


def check_nf_attachment(doc, method=None):
    """
    Hook called when a new Communication is created.

    Checks if the email contains NF attachments.
    """
    settings = frappe.get_single("Nota Fiscal Settings")

    if not settings.enabled or not settings.email_import_enabled:
        return

    if doc.communication_type != "Communication":
        return

    if doc.sent_or_received != "Received":
        return

    # Check if from configured email account
    if settings.email_account and doc.email_account != settings.email_account:
        return

    # Check subject patterns
    if settings.email_subject_patterns:
        patterns = settings.email_subject_patterns.split("\n")
        subject_matches = False

        for pattern in patterns:
            pattern = pattern.strip()
            if not pattern:
                continue

            if "*" in pattern:
                # Simple wildcard matching
                import fnmatch
                if fnmatch.fnmatch(doc.subject.lower(), pattern.lower()):
                    subject_matches = True
                    break
            elif pattern.lower() in doc.subject.lower():
                subject_matches = True
                break

        if not subject_matches:
            # Mark as processed (no match)
            frappe.db.set_value("Communication", doc.name, "nf_processed", 1)
            return

    # Queue processing
    frappe.enqueue(
        "brazil_nf.services.email_monitor.process_email",
        comm_name=doc.name,
        settings=None,  # Will reload
        queue="short"
    )


def process_email(comm_name, settings=None):
    """
    Process an email for NF attachments.

    Args:
        comm_name: Communication document name
        settings: Nota Fiscal Settings (optional)
    """
    if not settings:
        settings = frappe.get_single("Nota Fiscal Settings")

    comm = frappe.get_doc("Communication", comm_name)

    # Get attachments
    attachments = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Communication",
            "attached_to_name": comm_name
        },
        fields=["name", "file_name", "file_url"]
    )

    xml_found = False

    for attachment in attachments:
        file_name = attachment["file_name"].lower()

        # Check if it's an XML file
        if file_name.endswith(".xml"):
            try:
                process_xml_attachment(attachment, comm, settings)
                xml_found = True
            except Exception as e:
                frappe.log_error(str(e), f"Error processing XML from email: {comm_name}")

    # Mark as processed
    frappe.db.set_value("Communication", comm_name, "nf_processed", 1)

    if xml_found:
        frappe.logger().info(f"Processed NF attachments from email: {comm_name}")


def process_xml_attachment(attachment, comm, settings):
    """
    Process a single XML attachment.

    Args:
        attachment: File document data
        comm: Communication document
        settings: Nota Fiscal Settings
    """
    from brazil_nf.services.xml_parser import NFXMLParser

    # Read file content
    file_path = frappe.get_site_path(attachment["file_url"].lstrip("/"))

    with open(file_path, "r", encoding="utf-8") as f:
        xml_content = f.read()

    # Parse XML
    parser = NFXMLParser()
    data = parser.parse(xml_content)

    if not data:
        return

    # Check for duplicates
    chave = data.get("chave_de_acesso")

    if chave:
        existing = frappe.db.exists("Nota Fiscal", {"chave_de_acesso": chave})

        if existing:
            # Update origin flags
            nf_doc = frappe.get_doc("Nota Fiscal", existing)
            nf_doc.origin_email = 1
            nf_doc.email_reference = comm.name
            nf_doc.save(ignore_permissions=True)
            return

    # Create new Nota Fiscal
    nf_doc = frappe.new_doc("Nota Fiscal")
    nf_doc.company = settings.default_company

    # Set origin
    nf_doc.origin_email = 1
    nf_doc.email_reference = comm.name

    # Populate from parsed data
    for field, value in data.items():
        if hasattr(nf_doc, field) and value is not None:
            setattr(nf_doc, field, value)

    nf_doc.xml_content = xml_content
    nf_doc.insert(ignore_permissions=True)
