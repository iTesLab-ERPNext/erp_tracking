// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-devices"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Devices"),
		single_column: true,
	});

	const $container = $(`<div></div>`).appendTo(page.body);

	new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_devices",
		page_length: 20,
		columns: [
			{ label: __("Name"), field: "name" },
			{ label: __("Unique ID"), field: "uniqueId" },
			{ label: __("Status"), field: "status", format: (v) => erp_tracking.status_badge(v) },
			{
				label: __("Last Update"),
				field: "lastUpdate",
				format: (v) => (v ? frappe.datetime.prettyDate(v) : "—"),
			},
			{ label: __("Category"), field: "category", format: (v) => v || "—" },
			{ label: __("Model"), field: "model", format: (v) => v || "—" },
			{ label: __("Phone"), field: "phone", format: (v) => v || "—" },
			{
				label: __("Disabled"),
				field: "disabled",
				format: (v) => (v ? `<span class="indicator-pill danger">${__("Yes")}</span>` : `<span class="indicator-pill success">${__("No")}</span>`),
			},
		],
		on_row_click: (row) => show_device_details(row),
	}).load();
};

function show_device_details(device) {
	const dialog = new frappe.ui.Dialog({
		title: device.name || __("Device Details"),
		size: "large",
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "device_details_html",
			},
		],
	});

	dialog.show();
	render_overview(dialog, device);

	// Fetch the full record (list responses may exclude attributes when
	// excludeAttributes is used elsewhere; this guarantees the freshest data).
	frappe.call({
		method: "erp_tracking.api.get_device",
		args: { device_id: device.id },
		callback: (r) => {
			const result = r.message || {};
			if (result.success) {
				render_overview(dialog, result.data);
			}
		},
	});
}

function render_overview(dialog, device) {
	const rows = [
		[__("Device Name"), device.name],
		[__("Unique ID"), device.uniqueId],
		[__("Status"), erp_tracking.status_badge(device.status)],
		[__("Last Update"), device.lastUpdate ? frappe.datetime.prettyDate(device.lastUpdate) : "—"],
		[__("Category"), device.category || "—"],
		[__("Model"), device.model || "—"],
		[__("Phone"), device.phone || "—"],
		[__("Group"), device.groupId ?? "—"],
	];

	const table_rows = rows
		.map(([label, value]) => `<tr><th style="width:160px;">${label}</th><td>${value}</td></tr>`)
		.join("");

	dialog.fields_dict.device_details_html.$wrapper.html(`
		<ul class="nav nav-tabs mb-3">
			<li class="nav-item"><a class="nav-link active">${__("Overview")}</a></li>
			<li class="nav-item"><a class="nav-link disabled" title="${__("Available in a later phase")}">${__("Positions")}</a></li>
			<li class="nav-item"><a class="nav-link disabled" title="${__("Available in a later phase")}">${__("Trips")}</a></li>
			<li class="nav-item"><a class="nav-link disabled" title="${__("Available in a later phase")}">${__("Stops")}</a></li>
			<li class="nav-item"><a class="nav-link disabled" title="${__("Available in a later phase")}">${__("Events")}</a></li>
			<li class="nav-item"><a class="nav-link disabled" title="${__("Available in a later phase")}">${__("Maintenance")}</a></li>
			<li class="nav-item"><a class="nav-link disabled" title="${__("Available in a later phase")}">${__("Commands")}</a></li>
			<li class="nav-item"><a class="nav-link disabled" title="${__("Available in a later phase")}">${__("Geofences")}</a></li>
		</ul>
		<table class="table table-bordered">${table_rows}</table>
	`);
}
