// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["tracking_devices"].on_page_load = function (wrapper) {
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
	render_tabs(dialog, device);

	// Fetch the full record (list responses may exclude attributes when
	// excludeAttributes is used elsewhere; this guarantees the freshest data).
	frappe.call({
		method: "erp_tracking.api.get_device",
		args: { device_id: device.id },
		callback: (r) => {
			const result = r.message || {};
			if (result.success) {
				render_tabs(dialog, result.data);
			}
		},
	});
}

const IS_MANAGER = frappe.user_roles.some((r) => ["System Manager", "ERP Tracking Manager"].includes(r));

const TABS = [
	{ key: "overview", label: __("Overview"), available: true },
	{ key: "positions", label: __("Positions"), available: true },
	{ key: "trips", label: __("Trips"), available: true },
	{ key: "stops", label: __("Stops"), available: true },
	{ key: "events", label: __("Events"), available: true },
	{ key: "maintenance", label: __("Maintenance"), available: true },
	{ key: "commands", label: __("Commands"), available: IS_MANAGER, unavailable_reason: __("Manager only") },
	{ key: "geofences", label: __("Geofences"), available: true },
];

function render_tabs(dialog, device) {
	const $wrapper = dialog.fields_dict.device_details_html.$wrapper;
	const tab_links = TABS.map(
		(t) => `
			<li class="nav-item">
				<a class="nav-link ${t.key === "overview" ? "active" : ""} ${t.available ? "" : "disabled"}"
					data-tab="${t.key}" href="#"
					title="${t.available ? "" : t.unavailable_reason}">${t.label}</a>
			</li>
		`
	).join("");

	$wrapper.html(`
		<ul class="nav nav-tabs mb-3 erp-tracking-device-tabs">${tab_links}</ul>
		<div class="erp-tracking-device-tab-body"></div>
	`);

	const $tabBody = $wrapper.find(".erp-tracking-device-tab-body");

	const render_current = (tab_key) => {
		if (tab_key === "overview") return render_overview($tabBody, device);
		if (tab_key === "positions") return render_device_positions($tabBody, device);
		if (tab_key === "trips") return render_device_report($tabBody, device, "trips");
		if (tab_key === "stops") return render_device_report($tabBody, device, "stops");
		if (tab_key === "events") return render_device_report($tabBody, device, "events");
		if (tab_key === "maintenance") return render_device_maintenance($tabBody, device);
		if (tab_key === "commands") return render_device_commands($tabBody, device);
		if (tab_key === "geofences") return render_device_geofences($tabBody, device);
	};

	$wrapper.find(".erp-tracking-device-tabs a").on("click", (e) => {
		e.preventDefault();
		const $link = $(e.currentTarget);
		if ($link.hasClass("disabled")) return;
		$wrapper.find(".erp-tracking-device-tabs a").removeClass("active");
		$link.addClass("active");
		render_current($link.data("tab"));
	});

	render_current("overview");
}

function render_overview($wrapper, device) {
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

	$wrapper.html(`<table class="table table-bordered">${table_rows}</table>`);
}

function render_device_positions($wrapper, device) {
	$wrapper.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

	const from_date = frappe.datetime.add_days(frappe.datetime.now_datetime(), -1);
	const to_date = frappe.datetime.now_datetime();

	frappe.call({
		method: "erp_tracking.api.get_position_history",
		args: { device_id: device.id, from_date, to_date },
		callback: (r) => {
			const result = r.message || {};
			if (!result.success) {
				$wrapper.html(`<div class="text-muted text-center p-4">🔴 ${frappe.utils.escape_html(result.message || __("Unable to load positions."))}</div>`);
				return;
			}
			const positions = result.data || [];
			if (!positions.length) {
				$wrapper.html(`<div class="text-muted text-center p-4">${__("No positions in the last 24 hours.")}</div>`);
				return;
			}
			const rows = positions
				.slice(-20)
				.reverse()
				.map(
					(p) => `
					<tr>
						<td>${p.fixTime ? frappe.datetime.str_to_user(p.fixTime) : "—"}</td>
						<td>${(p.latitude ?? 0).toFixed(5)}</td>
						<td>${(p.longitude ?? 0).toFixed(5)}</td>
						<td>${(p.speed ?? 0).toFixed(1)} kn</td>
					</tr>
				`
				)
				.join("");
			$wrapper.html(`
				<div class="text-muted small mb-2">${__("Last 24 hours, most recent 20 shown. See Position History for the full range.")}</div>
				<table class="table table-bordered table-hover">
					<thead><tr><th>${__("Time")}</th><th>${__("Latitude")}</th><th>${__("Longitude")}</th><th>${__("Speed")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
			`);
		},
	});
}

function render_device_report($wrapper, device, report_key) {
	$wrapper.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

	const from_date = frappe.datetime.add_days(frappe.datetime.now_datetime(), -7);
	const to_date = frappe.datetime.now_datetime();

	frappe.call({
		method: "erp_tracking.api.get_report",
		args: {
			report_key,
			device_ids: JSON.stringify([device.id]),
			from_date,
			to_date,
		},
		callback: (r) => {
			const result = r.message || {};
			if (!result.success) {
				$wrapper.html(`<div class="text-muted text-center p-4">🔴 ${frappe.utils.escape_html(result.message || __("Unable to load report."))}</div>`);
				return;
			}
			const rows = result.data || [];
			if (!rows.length) {
				$wrapper.html(`<div class="text-muted text-center p-4">${__("No {0} in the last 7 days.", [report_key])}</div>`);
				return;
			}
			$wrapper.html(`
				<div class="text-muted small mb-2">${__("Last 7 days ({0} records). See Reports for full filters and export.", [rows.length])}</div>
				<pre style="max-height:300px; overflow:auto;">${frappe.utils.escape_html(JSON.stringify(rows.slice(0, 20), null, 2))}</pre>
			`);
		},
	});
}

function render_device_maintenance($wrapper, device) {
	$wrapper.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

	frappe.call({
		method: "erp_tracking.api.get_maintenance_items",
		args: { device_id: device.id },
		callback: (r) => {
			const result = r.message || {};
			if (!result.success) {
				$wrapper.html(`<div class="text-muted text-center p-4">🔴 ${frappe.utils.escape_html(result.message || __("Unable to load maintenance items."))}</div>`);
				return;
			}
			const items = result.data || [];
			if (!items.length) {
				$wrapper.html(`
					<div class="text-muted text-center p-4">${__("No maintenance items linked to this device.")}</div>
					<div class="text-center"><a href="/app/tracking_maintenance">${__("Open Maintenance")}</a></div>
				`);
				return;
			}
			const rows = items
				.map((m) => `<tr><td>${frappe.utils.escape_html(m.name)}</td><td>${frappe.utils.escape_html(m.type)}</td><td>${m.start}</td><td>${m.period}</td></tr>`)
				.join("");
			$wrapper.html(`
				<table class="table table-bordered table-hover">
					<thead><tr><th>${__("Name")}</th><th>${__("Type")}</th><th>${__("Start")}</th><th>${__("Period")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
			`);
		},
	});
}

function render_device_commands($tabBody, device) {
	$tabBody.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

	frappe.call({
		method: "erp_tracking.api.get_available_commands_for_device",
		args: { device_id: device.id },
		callback: (r) => {
			const result = r.message || {};
			if (!result.success) {
				$tabBody.html(`<div class="text-muted text-center p-4">🔴 ${frappe.utils.escape_html(result.message || __("Unable to load commands."))}</div>`);
				return;
			}
			const commands = result.data || [];
			if (!commands.length) {
				$tabBody.html(`<div class="text-muted text-center p-4">${__("No saved commands support this device's protocol.")}</div>`);
				return;
			}
			const rows = commands
				.map((c) => `<tr><td>${frappe.utils.escape_html(c.description || c.type)}</td><td>${frappe.utils.escape_html(c.type)}</td></tr>`)
				.join("");
			$tabBody.html(`
				<table class="table table-bordered table-hover">
					<thead><tr><th>${__("Description")}</th><th>${__("Type")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
				<div class="text-center mt-2"><a href="/app/tracking_commands">${__("Open Commands")}</a></div>
			`);
		},
	});
}

function render_device_geofences($wrapper, device) {
	$wrapper.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

	frappe.call({
		method: "erp_tracking.api.get_geofences",
		args: { device_id: device.id },
		callback: (r) => {
			const result = r.message || {};
			if (!result.success) {
				$wrapper.html(`<div class="text-muted text-center p-4">🔴 ${frappe.utils.escape_html(result.message || __("Unable to load geofences."))}</div>`);
				return;
			}
			const geofences = result.data || [];
			if (!geofences.length) {
				$wrapper.html(`
					<div class="text-muted text-center p-4">${__("No geofences linked to this device.")}</div>
					<div class="text-center"><a href="/app/tracking_geofences">${__("Open Geofences")}</a></div>
				`);
				return;
			}
			const rows = geofences
				.map((g) => `<tr><td>${frappe.utils.escape_html(g.name)}</td><td>${frappe.utils.escape_html(g.description || "—")}</td></tr>`)
				.join("");
			$wrapper.html(`
				<table class="table table-bordered table-hover">
					<thead><tr><th>${__("Name")}</th><th>${__("Description")}</th></tr></thead>
					<tbody>${rows}</tbody>
				</table>
			`);
		},
	});
}
