app_name = "brazil_nf"
app_title = "Brazil NF"
app_publisher = "Your Company"
app_description = "Brazilian Nota Fiscal Management for ERPNext - Captures NF-e, CT-e, and NFS-e"
app_email = "contact@yourcompany.com"
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/brazil_nf/css/brazil_nf.css"
# app_include_js = "/assets/brazil_nf/js/brazil_nf.js"

# include js, css files in header of web template
# web_include_css = "/assets/brazil_nf/css/brazil_nf.css"
# web_include_js = "/assets/brazil_nf/js/brazil_nf.js"

# include custom scss in every website theme (without signing in)
# website_theme_scss = "brazil_nf/public/scss/website"

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
    "Nota Fiscal": "brazil_nf/doctype/nota_fiscal/nota_fiscal.js"
}

doctype_list_js = {
    "Nota Fiscal": "brazil_nf/doctype/nota_fiscal/nota_fiscal_list.js"
}

# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "brazil_nf/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#     "Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#     "methods": "brazil_nf.utils.jinja_methods",
#     "filters": "brazil_nf.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "brazil_nf.install.before_install"
after_install = "brazil_nf.setup.install.after_install"
after_migrate = "brazil_nf.setup.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "brazil_nf.uninstall.before_uninstall"
# after_uninstall = "brazil_nf.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "brazil_nf.utils.before_app_install"
# after_app_install = "brazil_nf.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "brazil_nf.utils.before_app_uninstall"
# after_app_uninstall = "brazil_nf.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "brazil_nf.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#     "Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#     "Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#     "ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
    "Nota Fiscal": {
        "after_insert": "brazil_nf.services.processor.process_new_nf",
        "validate": "brazil_nf.services.processor.validate_nf"
    },
    "Communication": {
        "after_insert": "brazil_nf.services.email_monitor.check_nf_attachment"
    }
}

# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
        # Every 10 minutes - fetch documents from SEFAZ
        "*/10 * * * *": [
            "brazil_nf.services.dfe_client.scheduled_fetch"
        ],
        # Every 5 minutes - check emails for NF attachments
        "*/5 * * * *": [
            "brazil_nf.services.email_monitor.check_emails"
        ]
    },
    "daily": [
        "brazil_nf.services.processor.cleanup_old_logs"
    ],
    "weekly": [
        "brazil_nf.services.processor.cleanup_processed_xmls"
    ]
}

# Testing
# -------

# before_tests = "brazil_nf.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#     "frappe.desk.doctype.event.event.get_events": "brazil_nf.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#     "Task": "brazil_nf.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["brazil_nf.utils.before_request"]
# after_request = ["brazil_nf.utils.after_request"]

# Job Events
# ----------
# before_job = ["brazil_nf.utils.before_job"]
# after_job = ["brazil_nf.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#     {
#         "doctype": "{doctype_1}",
#         "filter_by": "{filter_by}",
#         "redact_fields": ["{field_1}", "{field_2}"],
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_2}",
#         "filter_by": "{filter_by}",
#         "partial": 1,
#     },
#     {
#         "doctype": "{doctype_3}",
#         "strict": False,
#     },
#     {
#         "doctype": "{doctype_4}"
#     }
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#     "brazil_nf.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# Fixtures
# --------
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "Brazil NF"]]
    },
    {
        "dt": "Property Setter",
        "filters": [["module", "=", "Brazil NF"]]
    },
    {
        "dt": "Role",
        "filters": [["name", "in", ["Brazil NF Manager", "Brazil NF User"]]]
    }
]
