// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on('NF Company Settings', {
    refresh: function(frm) {
        // Add custom buttons only for saved documents
        if (!frm.is_new()) {
            // Test Connection button - always show
            frm.add_custom_button(__('Test Connection'), function() {
                frappe.call({
                    method: 'brazil_nf.brazil_nf.doctype.nf_company_settings.nf_company_settings.test_connection',
                    args: {
                        company_settings_name: frm.doc.name
                    },
                    freeze: true,
                    freeze_message: __('Testing connection to SEFAZ...'),
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __('Connection Test'),
                                indicator: r.message.success ? 'green' : 'red',
                                message: r.message.message || JSON.stringify(r.message)
                            });
                        }
                    },
                    error: function(r) {
                        frappe.msgprint({
                            title: __('Error'),
                            indicator: 'red',
                            message: __('Failed to test connection. Check console for details.')
                        });
                    }
                });
            }, __('Actions'));

            // Fetch Now button
            frm.add_custom_button(__('Fetch from SEFAZ'), function() {
                frappe.prompt([
                    {
                        label: __('Document Type'),
                        fieldname: 'document_type',
                        fieldtype: 'Select',
                        options: '\nNF-e\nCT-e\nNFS-e',
                        description: __('Leave empty to fetch all enabled types')
                    }
                ], function(values) {
                    frappe.call({
                        method: 'brazil_nf.brazil_nf.doctype.nf_company_settings.nf_company_settings.fetch_documents',
                        args: {
                            company_settings_name: frm.doc.name,
                            document_type: values.document_type || null
                        },
                        freeze: true,
                        freeze_message: __('Fetching documents from SEFAZ...'),
                        callback: function(r) {
                            if (r.message) {
                                let msg = '';
                                let hasRateLimit = false;
                                if (typeof r.message === 'object') {
                                    for (let key in r.message) {
                                        let result = r.message[key];
                                        msg += `<b>${key}:</b><br>`;

                                        if (result.status === 'rate_limited') {
                                            hasRateLimit = true;
                                            msg += `&nbsp;&nbsp;<span style="color:orange">⏳ Rate Limited</span><br>`;
                                            if (result.wait_minutes) {
                                                msg += `&nbsp;&nbsp;Wait ${result.wait_minutes} minutes before next fetch<br>`;
                                            }
                                        } else {
                                            msg += `&nbsp;&nbsp;Fetched: ${result.fetched || 0}, Created: ${result.created || 0}<br>`;
                                        }

                                        if (result.sefaz_status) {
                                            msg += `&nbsp;&nbsp;SEFAZ Status: ${result.sefaz_status}<br>`;
                                        }
                                        if (result.nsu_used !== undefined) {
                                            msg += `&nbsp;&nbsp;NSU Used: ${result.nsu_used}<br>`;
                                        }
                                        if (result.message) {
                                            msg += `&nbsp;&nbsp;Message: ${result.message}<br>`;
                                        }
                                    }
                                } else {
                                    msg = JSON.stringify(r.message);
                                }
                                frappe.msgprint({
                                    title: __('Fetch Results'),
                                    indicator: hasRateLimit ? 'orange' : 'green',
                                    message: msg
                                });
                                frm.reload_doc();
                            }
                        },
                        error: function(r) {
                            frappe.msgprint({
                                title: __('Error'),
                                indicator: 'red',
                                message: __('Failed to fetch documents. Check console for details.')
                            });
                        }
                    });
                }, __('Fetch Documents'), __('Fetch'));
            }, __('Actions'));

            // View Logs button
            frm.add_custom_button(__('View Import Logs'), function() {
                frappe.set_route('List', 'NF Import Log', {
                    company: frm.doc.company
                });
            }, __('View'));

            // View Notas Fiscais button
            frm.add_custom_button(__('View Notas Fiscais'), function() {
                frappe.set_route('List', 'Nota Fiscal', {
                    company: frm.doc.company
                });
            }, __('View'));
        }

        // Certificate status indicator
        if (frm.doc.certificate_valid) {
            frm.dashboard.add_indicator(__('Certificate Valid'), 'green');
            if (frm.doc.certificate_expiry) {
                let today = frappe.datetime.get_today();
                let days_left = frappe.datetime.get_diff(frm.doc.certificate_expiry, today);

                if (days_left <= 30 && days_left > 0) {
                    frm.dashboard.add_indicator(
                        __('Expires in {0} days', [days_left]),
                        days_left <= 7 ? 'red' : 'orange'
                    );
                } else if (days_left <= 0) {
                    frm.dashboard.add_indicator(__('Certificate Expired'), 'red');
                }
            }
        } else if (frm.doc.certificate_file) {
            frm.dashboard.add_indicator(__('Certificate Invalid'), 'red');
        } else {
            frm.dashboard.add_indicator(__('No Certificate'), 'gray');
        }

        // Sync status indicator
        if (frm.doc.sync_enabled) {
            frm.dashboard.add_indicator(__('Sync Enabled'), 'blue');
        }
    },

    certificate_file: function(frm) {
        // When certificate file changes or is cleared
        if (!frm.doc.certificate_file) {
            // File was cleared - reset all certificate-related fields
            frm.set_value('certificate_valid', 0);
            frm.set_value('certificate_expiry', null);
            frm.set_value('certificate_password', '');
            frappe.show_alert({
                message: __('Certificate cleared. Please upload a new certificate.'),
                indicator: 'orange'
            });
        } else {
            // New file uploaded - reset validation
            frm.set_value('certificate_valid', 0);
            frm.set_value('certificate_expiry', null);
            frappe.show_alert({
                message: __('Certificate uploaded. Enter password and save to validate.'),
                indicator: 'blue'
            });
        }
    },

    certificate_password: function(frm) {
        // When password changes, reset validation
        if (frm.doc.certificate_file && frm.doc.certificate_password) {
            frm.set_value('certificate_valid', 0);
            frm.set_value('certificate_expiry', null);
        }
    }
});
