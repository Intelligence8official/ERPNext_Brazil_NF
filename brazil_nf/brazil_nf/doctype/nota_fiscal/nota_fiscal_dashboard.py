from frappe import _


def get_data():
    return {
        "heatmap": False,
        "fieldname": "nota_fiscal",
        "non_standard_fieldnames": {
            "Supplier": "supplier"
        },
        "transactions": [
            {
                "label": _("Related Documents"),
                "items": ["Purchase Invoice", "Purchase Order"]
            }
        ],
        "internal_links": {
            "Supplier": ["supplier"]
        }
    }
