// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["tracking_maintenance"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Maintenance"),
		single_column: true,
	});

	const can_write = frappe.user_roles.some((r) => ["System Manager", "ERP Tracking Manager", "ERP Tracking User"].includes(r));

	if (can_write) {
		page.set_primary_action(__("New Maintenance Item"), () => show_maintenance_dialog(null, () => list.load({ refresh: true })), "fa fa-plus");
	}

	const $filterBar = $(`
		<div class="d-flex mb-3" style="gap: 8px;">
			<select class="form-control erp-tracking-device-filter" style="max-width: 240px;">
				<option value="">${__("All Devices")}</option>
			</select>
		</div>
	`).appendTo(page.body);

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_maintenance_items",
		page_length: 20,
		columns: [
			{ label: __("Name"), field: "name" },
			{ label: __("Type"), field: "type" },
			{ label: __("Start"), field: "start" },
			{ label: __("Period"), field: "period" },
		],
		on_row_click: can_write ? (row) => show_maintenance_dialog(row, () => list.load({ refresh: true })) : null,
	});
	list.load();

	frappe.call({
		method: "erp_tracking.api.get_devices",
		args: { limit: 500 },
		callback: (r) => {
			const result = r.message || {};
			if (result.success) {
				(result.data || []).forEach((d) => {
					$filterBar.find(".erp-tracking-device-filter").append(`<option value="${d.id}">${frappe.utils.escape_html(d.name)}</option>`);
				});
			}
		},
	});

	$filterBar.find(".erp-tracking-device-filter").on("change", (e) => {
		list.extra_args = { device_id: $(e.currentTarget).val() || undefined };
		list.offset = 0;
		list.load();
	});
};

function show_maintenance_dialog(item, on_done) {
	const is_new = !item;

	const dialog = new frappe.ui.Dialog({
		title: is_new ? __("New Maintenance Item") : __("Edit Maintenance Item"),
		fields: [
			{ fieldtype: "Data", fieldname: "name", label: __("Name"), reqd: 1 },
			{
				fieldtype: "Data",
				fieldname: "type_",
				label: __("Type"),
				reqd: 1,
				description: __("Metric this maintenance tracks, e.g. totalDistance, hours"),
			},
			{ fieldtype: "Float", fieldname: "start", label: __("Start (current value)"), reqd: 1 },
			{ fieldtype: "Float", fieldname: "period", label: __("Period (threshold)"), reqd: 1 },
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
			const method = is_new ? "erp_tracking.api.create_maintenance_item" : "erp_tracking.api.update_maintenance_item";
			const args = is_new
				? { name: values.name, type_: values.type_, start: values.start, period: values.period, attributes: attributes ? JSON.stringify(attributes) : undefined }
				: { maintenance_id: item.id, name: values.name, type: values.type_, start: values.start, period: values.period, attributes };

			frappe.call({
				method,
				args,
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: is_new ? __("Maintenance item created.") : __("Maintenance item updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to save."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	if (!is_new) {
		dialog.set_values({
			name: item.name,
			type_: item.type,
			start: item.start,
			period: item.period,
			attributes: item.attributes && Object.keys(item.attributes).length ? JSON.stringify(item.attributes, null, 2) : "",
		});

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete maintenance item {0}?", [item.name]), () => {
				frappe.call({
					method: "erp_tracking.api.delete_maintenance_item",
					args: { maintenance_id: item.id },
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: __("Maintenance item deleted."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to delete."));
						}
					},
				});
			});
		});
	}

	dialog.show();
}
