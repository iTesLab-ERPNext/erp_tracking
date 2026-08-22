// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["tracking_orders"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Orders"),
		single_column: true,
	});

	const can_write = frappe.user_roles.some((r) => ["System Manager", "ERP Tracking Manager", "ERP Tracking User"].includes(r));

	if (can_write) {
		page.set_primary_action(__("New Order"), () => show_order_dialog(null, () => list.load({ refresh: true })), "fa fa-plus");
	}

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_orders",
		page_length: 20,
		columns: [
			{ label: __("Unique ID"), field: "uniqueId" },
			{ label: __("Description"), field: "description", format: (v) => v || "—" },
			{ label: __("From"), field: "fromAddress", format: (v) => v || "—" },
			{ label: __("To"), field: "toAddress", format: (v) => v || "—" },
		],
		on_row_click: can_write ? (row) => show_order_dialog(row, () => list.load({ refresh: true })) : null,
	});
	list.load();
};

function show_order_dialog(order, on_done) {
	const is_new = !order;

	const dialog = new frappe.ui.Dialog({
		title: is_new ? __("New Order") : __("Edit Order"),
		fields: [
			{ fieldtype: "Data", fieldname: "unique_id", label: __("Unique ID"), reqd: 1 },
			{ fieldtype: "Small Text", fieldname: "description", label: __("Description") },
			{ fieldtype: "Data", fieldname: "from_address", label: __("From Address") },
			{ fieldtype: "Data", fieldname: "to_address", label: __("To Address") },
			{ fieldtype: "Code", fieldname: "attributes", label: __("Attributes (JSON)"), options: "JSON" },
		],
		primary_action_label: is_new ? __("Create") : __("Save"),
		primary_action: (values) => {
			let attributes;
			if (values.attributes) {
				try {
					attributes = JSON.parse(values.attributes);
				} catch (e) {
					frappe.msgprint(__("Attributes must be valid JSON."));
					return;
				}
			}

			dialog.disable_primary_action();
			const method = is_new ? "erp_tracking.api.create_order" : "erp_tracking.api.update_order";
			const args = is_new
				? {
						unique_id: values.unique_id,
						description: values.description,
						from_address: values.from_address,
						to_address: values.to_address,
						attributes: attributes ? JSON.stringify(attributes) : undefined,
				  }
				: {
						order_id: order.id,
						uniqueId: values.unique_id,
						description: values.description,
						fromAddress: values.from_address,
						toAddress: values.to_address,
						attributes,
				  };

			frappe.call({
				method,
				args,
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: is_new ? __("Order created.") : __("Order updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to save order."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	if (!is_new) {
		dialog.set_values({
			unique_id: order.uniqueId,
			description: order.description,
			from_address: order.fromAddress,
			to_address: order.toAddress,
			attributes: order.attributes && Object.keys(order.attributes).length ? JSON.stringify(order.attributes, null, 2) : "",
		});

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete order {0}?", [order.uniqueId]), () => {
				frappe.call({
					method: "erp_tracking.api.delete_order",
					args: { order_id: order.id },
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: __("Order deleted."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to delete order."));
						}
					},
				});
			});
		});
	}

	dialog.show();
}
