// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on('NF Company Settings', {
    refresh: function(frm) {
        // Add custom buttons only for saved documents
        if (!frm.is_new()) {
            // Test Connection button
            frm.add_custom_button(__('Test Connection'), function() {
                frm.call({
                    method: 'test_connection',
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __('Testing connection to SEFAZ...'),
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __('Connection Test'),
                                indicator: r.message.success ? 'green' : 'red',
                                message: r.message.message || __('Connection test completed')
                            });
                        }
                    }
                });
            }, __('Actions'));

            // Fetch Now button - only show if certificate is valid
            if (frm.doc.certificate_valid) {
                frm.add_custom_button(__('Fetch from SEFAZ'), function() {
                    frappe.prompt([
                        {
                            label: __('Document Type'),
                            fieldname: 'document_type',
                            fieldtype: 'Select',
                            options: '\nNF-e\nCT-e\nNFS-e',
                            description: __('Leave empty to fetch all types')
                        }
                    ], function(values) {
                        frm.call({
                            method: 'fetch_now',
                            doc: frm.doc,
                            args: {
                                document_type: values.document_type || null
                            },
                            freeze: true,
                            freeze_message: __('Fetching documents from SEFAZ...'),
                            callback: function(r) {
                                if (r.message) {
                                    frappe.msgprint({
                                        title: __('Fetch Results'),
                                        indicator: 'green',
                                        message: __('Fetched {0} documents, Created {1} new records',
                                            [r.message.fetched || 0, r.message.created || 0])
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }, __('Fetch Documents'), __('Fetch'));
                }, __('Actions'));
            }

            // View Logs button
            frm.add_custom_button(__('View Import Logs'), function() {
                frappe.set_route('List', 'NF Import Log', {
                    company: frm.doc.company
                });
            }, __('Actions'));

            // View Notas Fiscais button
            frm.add_custom_button(__('View Notas Fiscais'), function() {
                frappe.set_route('List', 'Nota Fiscal', {
                    company: frm.doc.company
                });
            }, __('Actions'));
        }

        // Certificate status indicator
        if (frm.doc.certificate_valid) {
            frm.dashboard.add_indicator(__('Certificate Valid'), 'green');
            if (frm.doc.certificate_expiry) {
                let expiry = frappe.datetime.str_to_obj(frm.doc.certificate_expiry);
                let today = frappe.datetime.now_date();
                let days_left = frappe.datetime.get_diff(frm.doc.certificate_expiry, today);

                if (days_left <= 30) {
                    frm.dashboard.add_indicator(
                        __('Expires in {0} days', [days_left]),
                        days_left <= 7 ? 'red' : 'orange'
                    );
                }
            }
        } else if (frm.doc.certificate_file) {
            frm.dashboard.add_indicator(__('Certificate Invalid'), 'red');
        }

        // Sync status indicator
        if (frm.doc.sync_enabled) {
            frm.dashboard.add_indicator(__('Sync Enabled'), 'blue');
        }
    },

    certificate_file: function(frm) {
        // Clear validation when file changes
        if (frm.doc.certificate_file) {
            frm.set_value('certificate_valid', 0);
            frm.set_value('certificate_expiry', null);
        }
    },

    certificate_password: function(frm) {
        // Clear validation when password changes
        if (frm.doc.certificate_password) {
            frm.set_value('certificate_valid', 0);
            frm.set_value('certificate_expiry', null);
        }
    }
});
