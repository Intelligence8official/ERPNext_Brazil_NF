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
        'cancelada',
        'origin_sefaz',
        'origin_email'
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
            'Cancelled': ['Cancelled', 'red', 'processing_status,=,Cancelled'],
            'Error': ['Error', 'red', 'processing_status,=,Error']
        };

        return status_map[doc.processing_status] || ['Unknown', 'gray', ''];
    },

    formatters: {
        // Use simple text for status fields to avoid duplicate indicator pills
        supplier_status: function(value) {
            if (!value) return '';
            const icons = {
                'Pending': '⏳',
                'Linked': '✓',
                'Created': '✓',
                'Failed': '✗',
                'Not Found': '?'
            };
            return `${icons[value] || ''} ${__(value)}`;
        },

        item_creation_status: function(value) {
            if (!value) return '';
            const icons = {
                'Pending': '⏳',
                'All Created': '✓',
                'Partial': '⚠',
                'Failed': '✗'
            };
            return `${icons[value] || ''} ${__(value)}`;
        },

        po_status: function(value) {
            if (!value) return '';
            const icons = {
                'Pending': '⏳',
                'Linked': '✓',
                'Partial Match': '⚠',
                'Not Found': '?',
                'Not Applicable': '-'
            };
            return `${icons[value] || ''} ${__(value)}`;
        },

        document_type: function(value) {
            // Keep indicator pill only for document type as it's a key identifier
            const colors = {
                'NF-e': 'blue',
                'CT-e': 'purple',
                'NFS-e': 'cyan',
                'Invoice': 'green'
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
        },

        // Origin display - shows where the NF was captured from
        origin_sefaz: function(value, df, doc) {
            // Show combined origin badges
            let origins = [];
            if (doc.origin_sefaz) {
                origins.push('<span class="indicator-pill blue" title="SEFAZ API">API</span>');
            }
            if (doc.origin_email) {
                origins.push('<span class="indicator-pill orange" title="Email">Email</span>');
            }
            return origins.join(' ') || '<span class="text-muted">-</span>';
        }
    },

    // Default filters - show non-completed documents
    filters: [
        ['processing_status', 'not in', ['Completed', 'Cancelled']]
    ],

    onload: function(listview) {
        // Add SEFAZ menu with fetch and test options
        listview.page.add_menu_item(__('Fetch from SEFAZ'), function() {
            show_fetch_dialog(listview);
        }, true);

        listview.page.add_menu_item(__('Test Connection'), function() {
            show_test_connection_dialog();
        });

        listview.page.add_menu_item(__('Company Settings'), function() {
            frappe.set_route('List', 'NF Company Settings');
        });

        // Bulk actions
        listview.page.add_actions_menu_item(__('Process Selected'), function() {
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
        if (doc.cancelada || doc.processing_status === 'Cancelled') {
            return 'cancelled';
        }
        return '';
    },

    // Primary action button
    primary_action_label: __('Fetch from SEFAZ'),
    primary_action: function() {
        show_fetch_dialog();
    }
};

function show_fetch_dialog(listview) {
    // First, get list of enabled companies
    frappe.call({
        method: 'brazil_nf.api.get_enabled_companies',
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint({
                    title: __('No Companies Configured'),
                    message: __('Please configure at least one company with a valid certificate in NF Company Settings.'),
                    indicator: 'orange'
                });
                return;
            }

            const companies = r.message;
            const company_options = companies.map(c => ({
                label: `${c.company} (${c.cnpj || 'No CNPJ'})`,
                value: c.name,
                description: c.sefaz_environment || 'Production'
            }));

            // Show dialog
            const dialog = new frappe.ui.Dialog({
                title: __('Fetch Documents from SEFAZ'),
                fields: [
                    {
                        fieldname: 'company_settings',
                        fieldtype: 'Select',
                        label: __('Company'),
                        reqd: 1,
                        options: company_options.map(c => c.value).join('\n'),
                        description: __('Select the company to fetch documents for')
                    },
                    {
                        fieldname: 'document_type',
                        fieldtype: 'Select',
                        label: __('Document Type'),
                        options: '\nNF-e\nCT-e\nNFS-e',
                        description: __('Leave empty to fetch all enabled types')
                    },
                    {
                        fieldname: 'info_section',
                        fieldtype: 'Section Break',
                        label: __('Company Info')
                    },
                    {
                        fieldname: 'company_info',
                        fieldtype: 'HTML',
                        options: '<div id="company-info-display"></div>'
                    }
                ],
                primary_action_label: __('Fetch'),
                primary_action: function(values) {
                    dialog.hide();

                    frappe.call({
                        method: 'brazil_nf.api.fetch_for_company',
                        args: {
                            company_settings_name: values.company_settings,
                            document_type: values.document_type || null
                        },
                        freeze: true,
                        freeze_message: __('Fetching documents from SEFAZ...'),
                        callback: function(r) {
                            if (r.message) {
                                show_fetch_results(r.message);
                                if (listview) {
                                    listview.refresh();
                                }
                            }
                        },
                        error: function(r) {
                            frappe.msgprint({
                                title: __('Fetch Error'),
                                message: __('Failed to fetch documents. Check the error log for details.'),
                                indicator: 'red'
                            });
                        }
                    });
                }
            });

            // Update company info when selection changes
            dialog.fields_dict.company_settings.$input.on('change', function() {
                const selected = dialog.get_value('company_settings');
                const company = companies.find(c => c.name === selected);
                if (company) {
                    const env_badge = company.sefaz_environment === 'Homologation'
                        ? '<span class="badge badge-warning">Homologação</span>'
                        : '<span class="badge badge-success">Produção</span>';

                    const html = `
                        <div class="company-info-card" style="padding: 10px; background: var(--bg-light-gray); border-radius: 4px;">
                            <p><strong>CNPJ:</strong> ${company.cnpj || '-'}</p>
                            <p><strong>Ambiente:</strong> ${env_badge}</p>
                            <p><strong>Último NSU (NFS-e):</strong> ${company.last_nsu_nfse || '0'}</p>
                            <p><strong>Última Sincronização:</strong> ${company.last_sync ? frappe.datetime.str_to_user(company.last_sync) : 'Nunca'}</p>
                        </div>
                    `;
                    dialog.$wrapper.find('#company-info-display').html(html);
                }
            });

            dialog.show();

            // Trigger change to show first company info
            if (companies.length > 0) {
                dialog.set_value('company_settings', companies[0].name);
                dialog.fields_dict.company_settings.$input.trigger('change');
            }
        }
    });
}

function show_test_connection_dialog() {
    frappe.call({
        method: 'brazil_nf.api.get_enabled_companies',
        callback: function(r) {
            if (!r.message || r.message.length === 0) {
                frappe.msgprint({
                    title: __('No Companies Configured'),
                    message: __('Please configure at least one company with a valid certificate.'),
                    indicator: 'orange'
                });
                return;
            }

            const companies = r.message;

            const dialog = new frappe.ui.Dialog({
                title: __('Test SEFAZ Connection'),
                fields: [
                    {
                        fieldname: 'company_settings',
                        fieldtype: 'Select',
                        label: __('Company'),
                        reqd: 1,
                        options: companies.map(c => c.name).join('\n')
                    }
                ],
                primary_action_label: __('Test'),
                primary_action: function(values) {
                    frappe.call({
                        method: 'brazil_nf.api.test_company_connection',
                        args: {
                            company_settings_name: values.company_settings
                        },
                        freeze: true,
                        freeze_message: __('Testing connection...'),
                        callback: function(r) {
                            dialog.hide();
                            if (r.message) {
                                const result = r.message;
                                let msg = result.message || 'Test completed';
                                if (result.environment) {
                                    msg += `<br><br><b>Ambiente:</b> ${result.environment}`;
                                }
                                if (result.endpoint) {
                                    msg += `<br><b>Endpoint:</b> <code>${result.endpoint}</code>`;
                                }
                                frappe.msgprint({
                                    title: __('Connection Test'),
                                    message: msg,
                                    indicator: result.status === 'success' ? 'green' : 'red'
                                });
                            }
                        }
                    });
                }
            });

            dialog.show();
        }
    });
}

function show_fetch_results(results) {
    let msg = '';
    let has_error = false;
    let has_rate_limit = false;

    for (let doc_type in results) {
        const result = results[doc_type];
        msg += `<b>${doc_type}:</b><br>`;

        if (result.status === 'error') {
            has_error = true;
            msg += `&nbsp;&nbsp;<span style="color:red">Error: ${result.message}</span><br>`;
        } else if (result.status === 'rate_limited') {
            has_rate_limit = true;
            msg += `&nbsp;&nbsp;<span style="color:orange">⏳ Rate Limited - Wait ${result.wait_minutes} minutes</span><br>`;
        } else {
            msg += `&nbsp;&nbsp;Fetched: ${result.fetched || 0}, Created: ${result.created || 0}`;
            if (result.events) {
                msg += `, Events: ${result.events}`;
            }
            msg += '<br>';

            if (result.sefaz_status) {
                msg += `&nbsp;&nbsp;SEFAZ Status: ${result.sefaz_status}<br>`;
            }
            if (result.nsu_used !== undefined) {
                msg += `&nbsp;&nbsp;NSU Used: ${result.nsu_used}<br>`;
            }
        }

        if (result.environment) {
            msg += `&nbsp;&nbsp;Ambiente: ${result.environment}<br>`;
        }
        msg += '<br>';
    }

    frappe.msgprint({
        title: __('Fetch Results'),
        message: msg,
        indicator: has_error ? 'red' : (has_rate_limit ? 'orange' : 'green')
    });
}
