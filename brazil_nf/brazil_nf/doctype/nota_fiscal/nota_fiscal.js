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
            frm.add_custom_button(__('Link to Purchase Order'), function() {
                frappe.prompt({
                    fieldname: 'purchase_order',
                    fieldtype: 'Link',
                    options: 'Purchase Order',
                    label: __('Purchase Order'),
                    reqd: 1,
                    filters: {
                        'supplier': frm.doc.supplier || '',
                        'docstatus': ['<', 2]
                    }
                }, function(values) {
                    frm.set_value('purchase_order', values.purchase_order);
                    frm.set_value('po_status', 'Linked');
                    frm.save();
                }, __('Select Purchase Order'));
            }, __('Links'));

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
                }, __('Links'));
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
    // Remove previous stats section if exists
    frm.fields_dict.identification_section.$wrapper.find('.nf-stats-section').remove();

    // Build stats HTML
    let stats_html = `
        <div class="nf-stats-section" style="margin-bottom: 15px; padding: 10px; background: var(--bg-light-gray); border-radius: 4px;">
            <div style="font-weight: 500; margin-bottom: 8px;">${__('Processing Status')}</div>
            <div style="display: flex; gap: 15px; flex-wrap: wrap;">
    `;

    // Supplier status
    if (frm.doc.supplier_status) {
        stats_html += `
            <div>
                <span class="indicator-pill ${get_status_color(frm.doc.supplier_status)}">
                    ${__('Supplier')}: ${__(frm.doc.supplier_status)}
                </span>
            </div>
        `;
    }

    // Items status
    if (frm.doc.item_creation_status) {
        stats_html += `
            <div>
                <span class="indicator-pill ${get_status_color(frm.doc.item_creation_status)}">
                    ${__('Items')}: ${__(frm.doc.item_creation_status)}
                </span>
            </div>
        `;
    }

    // PO status
    if (frm.doc.po_status) {
        stats_html += `
            <div>
                <span class="indicator-pill ${get_status_color(frm.doc.po_status)}">
                    ${__('PO')}: ${__(frm.doc.po_status)}
                </span>
            </div>
        `;
    }

    // Invoice status
    if (frm.doc.invoice_status && frm.doc.invoice_status !== 'Pending') {
        stats_html += `
            <div>
                <span class="indicator-pill ${get_status_color(frm.doc.invoice_status)}">
                    ${__('Invoice')}: ${__(frm.doc.invoice_status)}
                </span>
            </div>
        `;
    }

    stats_html += `
            </div>
        </div>
    `;

    // Insert after the section break
    frm.fields_dict.identification_section.$wrapper.prepend(stats_html);
}
