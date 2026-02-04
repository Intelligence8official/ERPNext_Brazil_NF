// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.listview_settings['Nota Fiscal'] = {
    add_fields: [
        'processing_status',
        'supplier_status',
        'item_creation_status',
        'po_status',
        'invoice_status',
        'document_type',
        'cancelada'
    ],

    get_indicator: function(doc) {
        // Primary indicator based on processing status
        if (doc.cancelada) {
            return [__('Cancelled'), 'red', 'cancelada,=,1'];
        }

        const status_map = {
            'New': ['New', 'gray', 'processing_status,=,New'],
            'Parsed': ['Parsed', 'blue', 'processing_status,=,Parsed'],
            'Supplier Processing': ['Processing', 'blue', 'processing_status,=,Supplier Processing'],
            'Item Processing': ['Processing', 'blue', 'processing_status,=,Item Processing'],
            'PO Matching': ['Matching PO', 'blue', 'processing_status,=,PO Matching'],
            'Invoice Creation': ['Creating Invoice', 'blue', 'processing_status,=,Invoice Creation'],
            'Completed': ['Completed', 'green', 'processing_status,=,Completed'],
            'Error': ['Error', 'red', 'processing_status,=,Error']
        };

        return status_map[doc.processing_status] || ['Unknown', 'gray', ''];
    },

    formatters: {
        supplier_status: function(value) {
            const colors = {
                'Pending': 'gray',
                'Linked': 'green',
                'Created': 'blue',
                'Failed': 'red',
                'Not Found': 'orange'
            };
            const color = colors[value] || 'gray';
            return `<span class="indicator-pill ${color}">${__(value)}</span>`;
        },

        item_creation_status: function(value) {
            const colors = {
                'Pending': 'gray',
                'All Created': 'green',
                'Partial': 'yellow',
                'Failed': 'red'
            };
            const color = colors[value] || 'gray';
            return `<span class="indicator-pill ${color}">${__(value)}</span>`;
        },

        po_status: function(value) {
            const colors = {
                'Pending': 'gray',
                'Linked': 'green',
                'Partial Match': 'yellow',
                'Not Found': 'orange',
                'Not Applicable': 'gray'
            };
            const color = colors[value] || 'gray';
            return `<span class="indicator-pill ${color}">${__(value)}</span>`;
        },

        document_type: function(value) {
            const colors = {
                'NF-e': 'blue',
                'CT-e': 'purple',
                'NFS-e': 'cyan'
            };
            const color = colors[value] || 'gray';
            return `<span class="indicator-pill ${color}">${value}</span>`;
        },

        emitente_cnpj: function(value) {
            if (!value) return '';
            // Format CNPJ with mask
            const clean = value.replace(/\D/g, '');
            if (clean.length === 14) {
                return clean.replace(
                    /^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/,
                    '$1.$2.$3/$4-$5'
                );
            }
            return value;
        },

        valor_total: function(value, df, doc) {
            if (!value) return '';
            return format_currency(value, 'BRL');
        }
    },

    // Default filters - show non-completed documents
    filters: [
        ['processing_status', '!=', 'Completed']
    ],

    // Bulk actions
    onload: function(listview) {
        listview.page.add_inner_button(__('Process Selected'), function() {
            const selected = listview.get_checked_items();
            if (selected.length === 0) {
                frappe.msgprint(__('Please select at least one document'));
                return;
            }

            frappe.confirm(
                __('Process {0} selected document(s)?', [selected.length]),
                function() {
                    frappe.call({
                        method: 'brazil_nf.api.batch_process',
                        args: {
                            documents: selected.map(d => d.name)
                        },
                        freeze: true,
                        freeze_message: __('Processing documents...'),
                        callback: function(r) {
                            listview.refresh();
                            frappe.show_alert({
                                message: __('Processed {0} documents', [selected.length]),
                                indicator: 'green'
                            });
                        }
                    });
                }
            );
        });
    },

    // Row styling based on status
    get_row_class: function(doc) {
        if (doc.processing_status === 'Error') {
            return 'error';
        }
        if (doc.cancelada) {
            return 'cancelled';
        }
        return '';
    },

    // Button to trigger manual fetch
    primary_action_label: __('Fetch from SEFAZ'),
    primary_action: function() {
        frappe.call({
            method: 'brazil_nf.api.fetch_documents',
            freeze: true,
            freeze_message: __('Fetching documents from SEFAZ...'),
            callback: function(r) {
                frappe.show_alert({
                    message: __('Fetch initiated'),
                    indicator: 'green'
                });
            }
        });
    }
};
