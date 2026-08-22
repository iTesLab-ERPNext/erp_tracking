// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// Sections 20 and 21 ("Events" and "Event Report") are, per the OpenAPI
// spec, the exact same request: GET /reports/events (there is no bare
// GET /events list endpoint - see config.py). This page is that request
// rendered with event-type badges; Export XLSX / Email Report (from
// Section 21) are the same ReportPage export buttons used by Trips/Stops/
// Summary, just configured for the "events" report key.

frappe.pages["tracking_events"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Events"),
		single_column: true,
	});

	const $container = $(`<div></div>`).appendTo(page.body);

	new erp_tracking.ReportPage({
		wrapper: $container,
		report_key: "events",
		supports_event_types: true,
		columns: [
			{ label: __("Date"), field: "eventTime", format: (v) => (v ? frappe.datetime.str_to_user(v) : "—") },
			{ label: __("Device"), field: "deviceId", format: (v) => `#${v}` },
			{ label: __("Event Type"), field: "type", format: (v) => erp_tracking.event_badge(v) },
			{ label: __("Position"), field: "positionId", format: (v) => (v ? `#${v}` : "—") },
			{ label: __("Geofence"), field: "geofenceId", format: (v) => (v ? `#${v}` : "—") },
			{
				label: __("Attributes"),
				field: "attributes",
				format: (v) => (v && Object.keys(v).length ? `<code>${frappe.utils.escape_html(JSON.stringify(v))}</code>` : "—"),
			},
		],
	});
};
