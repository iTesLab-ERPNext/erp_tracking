// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["tracking_drivers"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Drivers"),
		single_column: true,
	});

	const can_write = frappe.user_roles.some((r) => ["System Manager", "ERP Tracking Manager", "ERP Tracking User"].includes(r));

	if (can_write) {
		page.set_primary_action(__("New Driver"), () => show_driver_dialog(null, () => list.load({ refresh: true })), "fa fa-plus");
	}

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_drivers",
		page_length: 20,
		columns: [
			{ label: __("Name"), field: "name" },
			{ label: __("Unique ID"), field: "uniqueId" },
			{
				label: __("Attributes"),
				field: "attributes",
				format: (v) => (v && Object.keys(v).length ? `<code>${frappe.utils.escape_html(JSON.stringify(v))}</code>` : "—"),
			},
		],
		on_row_click: can_write ? (row) => show_driver_dialog(row, () => list.load({ refresh: true })) : null,
	});
	list.load();
};

function show_driver_dialog(driver, on_done) {
	const is_new = !driver;

	const dialog = new frappe.ui.Dialog({
		title: is_new ? __("New Driver") : __("Edit Driver"),
		fields: [
			{ fieldtype: "Data", fieldname: "name", label: __("Name"), reqd: 1 },
			{ fieldtype: "Data", fieldname: "unique_id", label: __("Unique ID"), reqd: 1 },
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
			const method = is_new ? "erp_tracking.api.create_driver" : "erp_tracking.api.update_driver";
			const args = is_new
				? { name: values.name, unique_id: values.unique_id, attributes: attributes ? JSON.stringify(attributes) : undefined }
				: { driver_id: driver.id, name: values.name, uniqueId: values.unique_id, attributes };

			frappe.call({
				method,
				args,
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: is_new ? __("Driver created.") : __("Driver updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to save driver."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	if (!is_new) {
		dialog.set_values({
			name: driver.name,
			unique_id: driver.uniqueId,
			attributes: driver.attributes && Object.keys(driver.attributes).length ? JSON.stringify(driver.attributes, null, 2) : "",
		});

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete driver {0}?", [driver.name]), () => {
				frappe.call({
					method: "erp_tracking.api.delete_driver",
					args: { driver_id: driver.id },
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: __("Driver deleted."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to delete driver."));
						}
					},
				});
			});
		});
	}

	dialog.show();
}
