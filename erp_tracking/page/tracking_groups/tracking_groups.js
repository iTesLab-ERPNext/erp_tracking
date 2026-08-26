// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["tracking_groups"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Groups"),
		single_column: true,
	});

	const can_write = frappe.user_roles.some((r) => ["System Manager", "ERP Tracking Manager", "ERP Tracking User"].includes(r));

	if (can_write) {
		page.set_primary_action(__("New Group"), () => show_group_form_dialog(null, () => list.load({ refresh: true })), "fa fa-plus");
	}

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_groups",
		page_length: 20,
		columns: [
			{ label: __("Name"), field: "name" },
			{ label: __("Parent Group"), field: "groupId", format: (v) => v || "—" },
		],
		on_row_click: (row) => (can_write ? show_group_form_dialog(row, () => list.load({ refresh: true })) : show_group_devices(row)),
	});
	list.load();
};

function show_group_form_dialog(group, on_done) {
	const is_new = !group;

	const dialog = new frappe.ui.Dialog({
		title: is_new ? __("New Group") : __("Edit Group"),
		fields: [
			{ fieldtype: "Data", fieldname: "name", label: __("Name"), reqd: 1 },
			{ fieldtype: "Int", fieldname: "group_id", label: __("Parent Group ID") },
			{ fieldtype: "Code", fieldname: "attributes", label: __("Attributes (JSON)"), options: "JSON" },
			{ fieldtype: "HTML", fieldname: "view_devices_html" },
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
			const method = is_new ? "erp_tracking.api.create_group" : "erp_tracking.api.update_group";
			const args = is_new
				? { name: values.name, group_id: values.group_id, attributes: attributes ? JSON.stringify(attributes) : undefined }
				: { group_id: group.id, name: values.name, groupId: values.group_id, attributes };

			frappe.call({
				method,
				args,
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: is_new ? __("Group created.") : __("Group updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to save group."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	if (!is_new) {
		dialog.set_values({
			name: group.name,
			group_id: group.groupId,
			attributes: group.attributes && Object.keys(group.attributes).length ? JSON.stringify(group.attributes, null, 2) : "",
		});

		dialog.fields_dict.view_devices_html.$wrapper.html(
			`<button class="btn btn-default btn-sm erp-tracking-view-devices">${__("View Devices in Group")}</button>`
		);
		dialog.fields_dict.view_devices_html.$wrapper.find(".erp-tracking-view-devices").on("click", () => show_group_devices(group));

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete group {0}?", [group.name]), () => {
				frappe.call({
					method: "erp_tracking.api.delete_group",
					args: { group_id: group.id },
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: __("Group deleted."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to delete group."));
						}
					},
				});
			});
		});
	}

	dialog.show();
}

function show_group_devices(group) {
	const dialog = new frappe.ui.Dialog({
		title: __("Devices in {0}", [group.name]),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "group_devices_html" }],
	});

	dialog.show();
	dialog.fields_dict.group_devices_html.$wrapper.html(
		`<div class="text-muted text-center p-4">${__("Loading...")}</div>`
	);

	frappe.call({
		method: "erp_tracking.api.get_devices_in_group",
		args: { group_id: group.id },
		callback: (r) => {
			const result = r.message || {};
			if (!result.success) {
				dialog.fields_dict.group_devices_html.$wrapper.html(
					`<div class="text-muted text-center p-4">🔴 ${frappe.utils.escape_html(result.message || __("Unable to load devices."))}</div>`
				);
				return;
			}

			const devices = result.data || [];
			if (!devices.length) {
				dialog.fields_dict.group_devices_html.$wrapper.html(
					`<div class="text-muted text-center p-4">${__("No devices in this group.")}</div>`
				);
				return;
			}

			const rows = devices
				.map(
					(d) =>
						`<tr><td>${frappe.utils.escape_html(d.name)}</td><td>${erp_tracking.status_badge(d.status)}</td></tr>`
				)
				.join("");

			dialog.fields_dict.group_devices_html.$wrapper.html(`
				<table class="table table-bordered">
					<thead><tr><th>${__("Name")}</th><th>${__("Status")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
			`);
		},
	});
}
