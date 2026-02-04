"""
Installation hooks for Brazil NF module.
"""

import frappe
from frappe import _


def after_install():
    """Post-installation setup."""
    create_custom_fields()
    create_roles()


def after_migrate():
    """Run after bench migrate."""
    create_custom_fields()


def create_custom_fields():
    """Create custom fields on standard ERPNext doctypes."""
    custom_fields = {
        "Supplier": [
            {
                "fieldname": "brazil_section",
                "fieldtype": "Section Break",
                "label": "Brazil",
                "insert_after": "tax_id",
                "collapsible": 1
            },
            {
                "fieldname": "inscricao_estadual",
                "fieldtype": "Data",
                "label": "Inscricao Estadual (IE)",
                "insert_after": "brazil_section",
                "description": "State Registration Number"
            },
            {
                "fieldname": "inscricao_municipal",
                "fieldtype": "Data",
                "label": "Inscricao Municipal (IM)",
                "insert_after": "inscricao_estadual",
                "description": "Municipal Registration Number"
            }
        ],
        "Item": [
            {
                "fieldname": "brazil_section",
                "fieldtype": "Section Break",
                "label": "Brazil Fiscal",
                "insert_after": "description",
                "collapsible": 1
            },
            {
                "fieldname": "ncm_code",
                "fieldtype": "Data",
                "label": "NCM Code",
                "insert_after": "brazil_section",
                "description": "Nomenclatura Comum do Mercosul (8 digits)"
            },
            {
                "fieldname": "cest_code",
                "fieldtype": "Data",
                "label": "CEST Code",
                "insert_after": "ncm_code",
                "description": "Codigo Especificador da Substituicao Tributaria (7 digits)"
            },
            {
                "fieldname": "origem_mercadoria",
                "fieldtype": "Select",
                "label": "Product Origin",
                "insert_after": "cest_code",
                "options": "\n0 - Nacional\n1 - Estrangeira - Importacao Direta\n2 - Estrangeira - Adquirida no Mercado Interno\n3 - Nacional com mais de 40% conteudo importado\n4 - Nacional conforme processos produtivos\n5 - Nacional com conteudo importado inferior a 40%\n6 - Estrangeira sem similar nacional\n7 - Estrangeira com similar nacional\n8 - Nacional com conteudo importado superior a 70%",
                "description": "Origin code for ICMS calculation"
            }
        ],
        "Purchase Invoice": [
            {
                "fieldname": "brazil_nf_section",
                "fieldtype": "Section Break",
                "label": "Nota Fiscal Reference",
                "insert_after": "bill_date",
                "collapsible": 1
            },
            {
                "fieldname": "nota_fiscal",
                "fieldtype": "Link",
                "label": "Nota Fiscal",
                "options": "Nota Fiscal",
                "insert_after": "brazil_nf_section",
                "read_only": 1
            },
            {
                "fieldname": "chave_de_acesso",
                "fieldtype": "Data",
                "label": "Chave de Acesso",
                "insert_after": "nota_fiscal",
                "read_only": 1,
                "description": "44-digit NF-e/CT-e/NFS-e access key"
            }
        ],
        "Purchase Order": [
            {
                "fieldname": "brazil_nf_section",
                "fieldtype": "Section Break",
                "label": "Nota Fiscal Reference",
                "insert_after": "transaction_date",
                "collapsible": 1
            },
            {
                "fieldname": "nota_fiscal",
                "fieldtype": "Link",
                "label": "Nota Fiscal",
                "options": "Nota Fiscal",
                "insert_after": "brazil_nf_section",
                "read_only": 1
            }
        ],
        "Communication": [
            {
                "fieldname": "nf_processed",
                "fieldtype": "Check",
                "label": "NF Processed",
                "default": "0",
                "hidden": 1,
                "insert_after": "seen",
                "description": "Indicates if this email was processed for NF attachments"
            }
        ]
    }

    for doctype, fields in custom_fields.items():
        for field in fields:
            field_name = f"{doctype}-{field['fieldname']}"

            # Check if field already exists
            if frappe.db.exists("Custom Field", field_name):
                continue

            # Create custom field
            custom_field = frappe.new_doc("Custom Field")
            custom_field.dt = doctype
            custom_field.module = "Brazil NF"

            for key, value in field.items():
                if hasattr(custom_field, key):
                    setattr(custom_field, key, value)

            try:
                custom_field.insert(ignore_permissions=True)
                frappe.logger().info(f"Created custom field: {field_name}")
            except Exception as e:
                frappe.logger().error(f"Error creating custom field {field_name}: {str(e)}")

    frappe.db.commit()


def create_roles():
    """Create custom roles for Brazil NF module."""
    roles = [
        {
            "role_name": "Brazil NF Manager",
            "desk_access": 1,
            "description": "Can manage all Brazil NF settings and documents"
        },
        {
            "role_name": "Brazil NF User",
            "desk_access": 1,
            "description": "Can view and process Brazil NF documents"
        }
    ]

    for role_data in roles:
        role_name = role_data.pop("role_name")

        if frappe.db.exists("Role", role_name):
            continue

        role = frappe.new_doc("Role")
        role.name = role_name

        for key, value in role_data.items():
            if hasattr(role, key):
                setattr(role, key, value)

        try:
            role.insert(ignore_permissions=True)
            frappe.logger().info(f"Created role: {role_name}")
        except Exception as e:
            frappe.logger().error(f"Error creating role {role_name}: {str(e)}")

    frappe.db.commit()
