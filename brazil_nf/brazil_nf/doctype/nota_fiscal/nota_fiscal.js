// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on('Nota Fiscal', {
    refresh: function(frm) {
        // Add custom buttons based on status
        if (!frm.is_new()) {
            frm.add_custom_button(__('Process Document'), function() {
                frm.call({
                    method: 'process_document',
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __('Processing...'),
                    callback: function(r) {
                        if (r.message) {
                            frm.reload_doc();
                            frappe.show_alert({
                                message: __('Document processed successfully'),
                                indicator: 'green'
                            });
                        }
                    }
                });
            }, __('Actions'));

            // Parse XML button
            if (frm.doc.xml_content && frm.doc.processing_status === 'New') {
                frm.add_custom_button(__('Parse XML'), function() {
                    frm.call({
                        method: 'parse_xml',
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __('Parsing XML...'),
                        callback: function(r) {
                            if (r.message) {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: __('XML parsed successfully'),
                                    indicator: 'green'
                                });
                            }
                        }
                    });
                }, __('Actions'));
            }

            // Create Supplier button
            if (frm.doc.supplier_status === 'Not Found' || frm.doc.supplier_status === 'Pending') {
                frm.add_custom_button(__('Create Supplier'), function() {
                    frm.call({
                        method: 'create_supplier',
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __('Creating supplier...'),
                        callback: function(r) {
                            if (r.message) {
                                frm.reload_doc();
                                if (r.message.supplier) {
                                    frappe.show_alert({
                                        message: __('Supplier {0} created/linked', [r.message.supplier]),
                                        indicator: 'green'
                                    });
                                }
                            }
                        }
                    });
                }, __('Actions'));
            }

            // Create Items button
            if (frm.doc.item_creation_status !== 'All Created') {
                frm.add_custom_button(__('Create Items'), function() {
                    frm.call({
                        method: 'create_items',
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __('Creating items...'),
                        callback: function(r) {
                            if (r.message) {
                                frm.reload_doc();
                                frappe.show_alert({
                                    message: __('Created {0} of {1} items', [r.message.created, r.message.total]),
                                    indicator: r.message.status === 'All Created' ? 'green' : 'orange'
                                });
                            }
                        }
                    });
                }, __('Actions'));
            }

            // Match PO button
            if (frm.doc.po_status === 'Pending' || frm.doc.po_status === 'Not Found') {
                frm.add_custom_button(__('Match Purchase Order'), function() {
                    frm.call({
                        method: 'match_purchase_order',
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __('Matching PO...'),
                        callback: function(r) {
                            if (r.message) {
                                frm.reload_doc();
                                if (r.message.purchase_order) {
                                    frappe.show_alert({
                                        message: __('Matched with PO: {0}', [r.message.purchase_order]),
                                        indicator: 'green'
                                    });
                                } else {
                                    frappe.show_alert({
                                        message: __('No matching PO found'),
                                        indicator: 'orange'
                                    });
                                }
                            }
                        }
                    });
                }, __('Actions'));
            }

            // Create Invoice button
            if (frm.doc.supplier && !frm.doc.purchase_invoice && frm.doc.processing_status !== 'Error') {
                frm.add_custom_button(__('Create Purchase Invoice'), function() {
                    frappe.confirm(
                        __('Create Purchase Invoice from this Nota Fiscal?'),
                        function() {
                            frm.call({
                                method: 'create_purchase_invoice',
                                doc: frm.doc,
                                args: { submit: false },
                                freeze: true,
                                freeze_message: __('Creating invoice...'),
                                callback: function(r) {
                                    if (r.message && r.message.invoice) {
                                        frm.reload_doc();
                                        frappe.show_alert({
                                            message: __('Invoice {0} created', [r.message.invoice]),
                                            indicator: 'green'
                                        });
                                    }
                                }
                            });
                        }
                    );
                }, __('Actions'));
            }

            // Link to existing PO
            if (!frm.doc.purchase_order) {
                frm.add_custom_button(__('Link to Purchase Order'), function() {
                    show_link_po_dialog(frm);
                }, __('Link to Existing'));
            }

            // Link to existing Purchase Invoice
            if (!frm.doc.purchase_invoice) {
                frm.add_custom_button(__('Link to Purchase Invoice'), function() {
                    show_link_invoice_dialog(frm);
                }, __('Link to Existing'));
            }

            // Link to existing Supplier
            if (!frm.doc.supplier) {
                frm.add_custom_button(__('Link to Supplier'), function() {
                    frappe.prompt({
                        fieldname: 'supplier',
                        fieldtype: 'Link',
                        options: 'Supplier',
                        label: __('Supplier'),
                        reqd: 1
                    }, function(values) {
                        frm.set_value('supplier', values.supplier);
                        frm.set_value('supplier_status', 'Linked');
                        frm.save();
                    }, __('Select Supplier'));
                }, __('Link to Existing'));
            }

            // Find matching documents button
            frm.add_custom_button(__('Find Matching Documents'), function() {
                find_matching_documents(frm);
            }, __('Link to Existing'));

            // Unlink Purchase Invoice
            if (frm.doc.purchase_invoice) {
                frm.add_custom_button(__('Unlink Purchase Invoice'), function() {
                    frappe.confirm(
                        __('Are you sure you want to unlink Purchase Invoice {0} from this Nota Fiscal?', [frm.doc.purchase_invoice]),
                        function() {
                            unlink_purchase_invoice(frm);
                        }
                    );
                }, __('Unlink'));
            }

            // Unlink Purchase Order
            if (frm.doc.purchase_order) {
                frm.add_custom_button(__('Unlink Purchase Order'), function() {
                    frappe.confirm(
                        __('Are you sure you want to unlink Purchase Order {0} from this Nota Fiscal?', [frm.doc.purchase_order]),
                        function() {
                            unlink_purchase_order(frm);
                        }
                    );
                }, __('Unlink'));
            }

            // Unlink Supplier
            if (frm.doc.supplier) {
                frm.add_custom_button(__('Unlink Supplier'), function() {
                    frappe.confirm(
                        __('Are you sure you want to unlink Supplier {0} from this Nota Fiscal?', [frm.doc.supplier]),
                        function() {
                            frm.set_value('supplier', null);
                            frm.set_value('supplier_status', 'Pending');
                            frm.save().then(() => {
                                frappe.show_alert({
                                    message: __('Supplier unlinked successfully'),
                                    indicator: 'green'
                                });
                            });
                        }
                    );
                }, __('Unlink'));
            }
        }

        // Add status section using custom HTML to avoid duplication
        show_processing_stats(frm);
    },

    document_type: function(frm) {
        // Update naming series based on document type
        if (frm.doc.document_type === 'NF-e') {
            frm.set_value('naming_series', 'NFE-.#####');
        } else if (frm.doc.document_type === 'CT-e') {
            frm.set_value('naming_series', 'CTE-.#####');
        } else if (frm.doc.document_type === 'NFS-e') {
            frm.set_value('naming_series', 'NFSE-.#####');
        }
    },

    chave_de_acesso: function(frm) {
        // Validate access key format
        if (frm.doc.chave_de_acesso) {
            let key = frm.doc.chave_de_acesso.replace(/\s/g, '');
            if (key.length !== 44) {
                frappe.msgprint(__('Access key must be 44 digits'));
            } else if (!/^\d+$/.test(key)) {
                frappe.msgprint(__('Access key must contain only digits'));
            } else {
                // Format with spaces for readability
                frm.set_value('chave_de_acesso', key);
            }
        }
    }
});

function get_status_color(status) {
    const colors = {
        'Pending': 'gray',
        'Linked': 'green',
        'Created': 'blue',
        'Failed': 'red',
        'Not Found': 'orange',
        'All Created': 'green',
        'Partial': 'yellow',
        'Partial Match': 'yellow',
        'Not Applicable': 'gray',
        'New': 'gray',
        'Completed': 'green',
        'Error': 'red',
        'Submitted': 'green'
    };
    return colors[status] || 'gray';
}

function show_processing_stats(frm) {
    // Use dashboard for stats to avoid issues with field wrappers
    // Clear any existing custom stats
    frm.dashboard.stats_area_row && frm.dashboard.stats_area_row.empty();

    // Show origin indicators first
    let origins = [];
    if (frm.doc.origin_sefaz) {
        origins.push('SEFAZ');
    }
    if (frm.doc.origin_email) {
        origins.push('Email');
    }
    if (origins.length > 0) {
        frm.dashboard.add_indicator(
            __('Origin: {0}', [origins.join(' + ')]),
            origins.length > 1 ? 'purple' : (frm.doc.origin_sefaz ? 'blue' : 'orange')
        );
    }

    // Add stats using dashboard indicators
    if (frm.doc.supplier_status) {
        frm.dashboard.add_indicator(
            __('Supplier: {0}', [__(frm.doc.supplier_status)]),
            get_status_color(frm.doc.supplier_status)
        );
    }

    if (frm.doc.item_creation_status) {
        frm.dashboard.add_indicator(
            __('Items: {0}', [__(frm.doc.item_creation_status)]),
            get_status_color(frm.doc.item_creation_status)
        );
    }

    if (frm.doc.po_status) {
        frm.dashboard.add_indicator(
            __('PO: {0}', [__(frm.doc.po_status)]),
            get_status_color(frm.doc.po_status)
        );
    }

    if (frm.doc.invoice_status && frm.doc.invoice_status !== 'Pending') {
        frm.dashboard.add_indicator(
            __('Invoice: {0}', [__(frm.doc.invoice_status)]),
            get_status_color(frm.doc.invoice_status)
        );
    }
}

function show_link_po_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Link to Purchase Order'),
        fields: [
            {
                fieldname: 'info',
                fieldtype: 'HTML',
                options: `<p>${__('Select a Purchase Order to link with this Nota Fiscal.')}</p>
                    <p><strong>${__('NF Value')}:</strong> R$ ${(frm.doc.valor_total || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</p>
                    <p><strong>${__('Supplier')}:</strong> ${frm.doc.emitente_razao_social || frm.doc.supplier || '-'}</p>`
            },
            {
                fieldname: 'purchase_order',
                fieldtype: 'Link',
                options: 'Purchase Order',
                label: __('Purchase Order'),
                reqd: 1,
                get_query: function() {
                    return {
                        filters: {
                            'supplier': frm.doc.supplier || ['is', 'set'],
                            'docstatus': ['<', 2],
                            'status': ['not in', ['Closed', 'Cancelled']]
                        }
                    };
                }
            }
        ],
        primary_action_label: __('Link'),
        primary_action: function(values) {
            frm.set_value('purchase_order', values.purchase_order);
            frm.set_value('po_status', 'Linked');
            frm.save().then(() => {
                dialog.hide();
                frappe.show_alert({
                    message: __('Purchase Order linked successfully'),
                    indicator: 'green'
                });
            });
        }
    });
    dialog.show();
}

function show_link_invoice_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Link to Purchase Invoice'),
        fields: [
            {
                fieldname: 'info',
                fieldtype: 'HTML',
                options: `<p>${__('Select a Purchase Invoice to link with this Nota Fiscal.')}</p>
                    <p><strong>${__('NF Number')}:</strong> ${frm.doc.numero || '-'}</p>
                    <p><strong>${__('NF Value')}:</strong> R$ ${(frm.doc.valor_total || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</p>
                    <p><strong>${__('Supplier')}:</strong> ${frm.doc.emitente_razao_social || frm.doc.supplier || '-'}</p>`
            },
            {
                fieldname: 'purchase_invoice',
                fieldtype: 'Link',
                options: 'Purchase Invoice',
                label: __('Purchase Invoice'),
                reqd: 1,
                get_query: function() {
                    return {
                        filters: {
                            'supplier': frm.doc.supplier || ['is', 'set'],
                            'docstatus': ['<', 2]
                        }
                    };
                }
            }
        ],
        primary_action_label: __('Link'),
        primary_action: function(values) {
            frappe.call({
                method: 'brazil_nf.api.link_purchase_invoice',
                args: {
                    nota_fiscal_name: frm.doc.name,
                    purchase_invoice_name: values.purchase_invoice
                },
                freeze: true,
                freeze_message: __('Linking...'),
                callback: function(r) {
                    if (r.message && r.message.status === 'success') {
                        dialog.hide();
                        frm.reload_doc();
                        frappe.show_alert({
                            message: __('Purchase Invoice linked successfully'),
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    });
    dialog.show();
}

function find_matching_documents(frm) {
    frappe.call({
        method: 'brazil_nf.api.find_matching_documents',
        args: {
            nota_fiscal_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Searching for matching documents...'),
        callback: function(r) {
            if (r.message) {
                show_matching_documents_dialog(frm, r.message);
            }
        }
    });
}

function show_matching_documents_dialog(frm, matches) {
    let html = '<div class="matching-documents">';

    // Purchase Invoices
    html += `<h5>${__('Purchase Invoices')}</h5>`;
    if (matches.invoices && matches.invoices.length > 0) {
        html += '<table class="table table-bordered table-sm"><thead><tr>';
        html += `<th>${__('Invoice')}</th><th>${__('Date')}</th><th>${__('Value')}</th><th>${__('Bill No')}</th><th></th>`;
        html += '</tr></thead><tbody>';
        matches.invoices.forEach(inv => {
            html += `<tr>
                <td><a href="/app/purchase-invoice/${inv.name}" target="_blank">${inv.name}</a></td>
                <td>${inv.posting_date || '-'}</td>
                <td>R$ ${(inv.grand_total || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                <td>${inv.bill_no || '-'}</td>
                <td><button class="btn btn-xs btn-primary link-invoice" data-invoice="${inv.name}">${__('Link')}</button></td>
            </tr>`;
        });
        html += '</tbody></table>';
    } else {
        html += `<p class="text-muted">${__('No matching Purchase Invoices found')}</p>`;
    }

    // Purchase Orders
    html += `<h5 style="margin-top: 15px;">${__('Purchase Orders')}</h5>`;
    if (matches.orders && matches.orders.length > 0) {
        html += '<table class="table table-bordered table-sm"><thead><tr>';
        html += `<th>${__('Order')}</th><th>${__('Date')}</th><th>${__('Value')}</th><th>${__('Status')}</th><th></th>`;
        html += '</tr></thead><tbody>';
        matches.orders.forEach(po => {
            html += `<tr>
                <td><a href="/app/purchase-order/${po.name}" target="_blank">${po.name}</a></td>
                <td>${po.transaction_date || '-'}</td>
                <td>R$ ${(po.grand_total || 0).toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
                <td>${po.status || '-'}</td>
                <td><button class="btn btn-xs btn-primary link-po" data-po="${po.name}">${__('Link')}</button></td>
            </tr>`;
        });
        html += '</tbody></table>';
    } else {
        html += `<p class="text-muted">${__('No matching Purchase Orders found')}</p>`;
    }

    html += '</div>';

    const dialog = new frappe.ui.Dialog({
        title: __('Matching Documents Found'),
        fields: [
            {
                fieldname: 'matches_html',
                fieldtype: 'HTML',
                options: html
            }
        ]
    });

    dialog.show();

    // Handle link button clicks
    dialog.$wrapper.find('.link-invoice').on('click', function() {
        const invoice_name = $(this).data('invoice');
        frappe.call({
            method: 'brazil_nf.api.link_purchase_invoice',
            args: {
                nota_fiscal_name: frm.doc.name,
                purchase_invoice_name: invoice_name
            },
            callback: function(r) {
                if (r.message && r.message.status === 'success') {
                    dialog.hide();
                    frm.reload_doc();
                    frappe.show_alert({
                        message: __('Purchase Invoice linked successfully'),
                        indicator: 'green'
                    });
                }
            }
        });
    });

    dialog.$wrapper.find('.link-po').on('click', function() {
        const po_name = $(this).data('po');
        frm.set_value('purchase_order', po_name);
        frm.set_value('po_status', 'Linked');
        frm.save().then(() => {
            dialog.hide();
            frappe.show_alert({
                message: __('Purchase Order linked successfully'),
                indicator: 'green'
            });
        });
    });
}

function unlink_purchase_invoice(frm) {
    frappe.call({
        method: 'brazil_nf.api.unlink_purchase_invoice',
        args: {
            nota_fiscal_name: frm.doc.name
        },
        freeze: true,
        freeze_message: __('Unlinking...'),
        callback: function(r) {
            if (r.message && r.message.status === 'success') {
                frm.reload_doc();
                frappe.show_alert({
                    message: __('Purchase Invoice unlinked successfully. You can now delete it if needed.'),
                    indicator: 'green'
                });
            }
        }
    });
}

function unlink_purchase_order(frm) {
    frm.set_value('purchase_order', null);
    frm.set_value('po_status', 'Pending');
    frm.save().then(() => {
        frappe.show_alert({
            message: __('Purchase Order unlinked successfully'),
            indicator: 'green'
        });
    });
}
