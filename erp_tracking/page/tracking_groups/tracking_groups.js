// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-groups"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Groups"),
		single_column: true,
	});

	const $container = $(`<div></div>`).appendTo(page.body);

	new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_groups",
		page_length: 20,
		columns: [
			{ label: __("Name"), field: "name" },
			{ label: __("Parent Group"), field: "groupId", format: (v) => v || "—" },
		],
		on_row_click: (row) => show_group_devices(row),
	}).load();
};

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
