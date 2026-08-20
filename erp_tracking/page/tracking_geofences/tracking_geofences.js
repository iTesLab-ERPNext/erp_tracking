// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-geofences"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Geofences"),
		single_column: true,
	});

	const can_write = frappe.user_roles.some((r) => ["System Manager", "ERP Tracking Manager", "ERP Tracking User"].includes(r));

	if (can_write) {
		page.set_primary_action(__("New Geofence"), () => show_geofence_dialog(null, () => list.load({ refresh: true })), "fa fa-plus");
	}

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_geofences",
		page_length: 20,
		columns: [
			{ label: __("Name"), field: "name" },
			{ label: __("Description"), field: "description", format: (v) => v || "—" },
			{ label: __("Calendar"), field: "calendarId", format: (v) => v || "—" },
		],
		on_row_click: can_write ? (row) => show_geofence_dialog(row, () => list.load({ refresh: true })) : null,
	});
	list.load();
};

function show_geofence_dialog(geofence, on_done) {
	const is_new = !geofence;

	const dialog = new frappe.ui.Dialog({
		title: is_new ? __("New Geofence") : __("Edit Geofence"),
		fields: [
			{ fieldtype: "Data", fieldname: "name", label: __("Name"), reqd: 1 },
			{ fieldtype: "Small Text", fieldname: "description", label: __("Description") },
			{
				fieldtype: "Small Text",
				fieldname: "area",
				label: __("Area (WKT)"),
				reqd: 1,
				description: __('e.g. CIRCLE (-27.5 153.0, 500) or POLYGON ((...))'),
			},
			{ fieldtype: "Int", fieldname: "calendar_id", label: __("Calendar ID") },
		],
		primary_action_label: is_new ? __("Create") : __("Save"),
		primary_action: (values) => {
			dialog.disable_primary_action();
			const method = is_new ? "erp_tracking.api.create_geofence" : "erp_tracking.api.update_geofence";
			const args = is_new
				? values
				: { geofence_id: geofence.id, name: values.name, description: values.description, area: values.area, calendarId: values.calendar_id };

			frappe.call({
				method,
				args,
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: is_new ? __("Geofence created.") : __("Geofence updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to save geofence."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	if (!is_new) {
		dialog.set_values({
			name: geofence.name,
			description: geofence.description,
			area: geofence.area,
			calendar_id: geofence.calendarId,
		});

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete geofence {0}? This cannot be undone.", [geofence.name]), () => {
				frappe.call({
					method: "erp_tracking.api.delete_geofence",
					args: { geofence_id: geofence.id },
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: __("Geofence deleted."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to delete geofence."));
						}
					},
				});
			});
		});
	}

	dialog.show();
}
