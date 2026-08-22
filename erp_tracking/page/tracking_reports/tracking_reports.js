// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["tracking_reports"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Reports"),
		single_column: true,
	});

	new ReportsHubPage(page);
};

function fmt_duration(seconds) {
	if (seconds == null) return "—";
	const h = Math.floor(seconds / 3600);
	const m = Math.floor((seconds % 3600) / 60);
	return `${h}h ${m}m`;
}

function fmt_km(meters) {
	if (meters == null) return "—";
	return `${(meters / 1000).toFixed(2)} km`;
}

function fmt_speed(knots) {
	if (knots == null) return "—";
	return `${knots.toFixed(1)} kn`;
}

const TAB_CONFIG = {
	trips: {
		label: __("Trips"),
		columns: [
			{ label: __("Device"), field: "deviceName" },
			{ label: __("Start Time"), field: "startTime", format: (v) => (v ? frappe.datetime.str_to_user(v) : "—") },
			{ label: __("End Time"), field: "endTime", format: (v) => (v ? frappe.datetime.str_to_user(v) : "—") },
			{ label: __("Start Address"), field: "startAddress", format: (v) => v || "—" },
			{ label: __("End Address"), field: "endAddress", format: (v) => v || "—" },
			{ label: __("Distance"), field: "distance", format: fmt_km },
			{ label: __("Duration"), field: "duration", format: fmt_duration },
			{ label: __("Average Speed"), field: "averageSpeed", format: fmt_speed },
			{ label: __("Maximum Speed"), field: "maxSpeed", format: fmt_speed },
		],
	},
	stops: {
		label: __("Stops"),
		columns: [
			{ label: __("Device"), field: "deviceName" },
			{ label: __("Start"), field: "startTime", format: (v) => (v ? frappe.datetime.str_to_user(v) : "—") },
			{ label: __("End"), field: "endTime", format: (v) => (v ? frappe.datetime.str_to_user(v) : "—") },
			{ label: __("Duration"), field: "duration", format: fmt_duration },
			{ label: __("Address"), field: "address", format: (v) => v || "—" },
			{ label: __("Latitude"), field: "lat", format: (v) => (v != null ? v.toFixed(5) : "—") },
			{ label: __("Longitude"), field: "lon", format: (v) => (v != null ? v.toFixed(5) : "—") },
		],
	},
	summary: {
		label: __("Summary"),
		supports_daily: true,
		columns: [
			{ label: __("Device"), field: "deviceName" },
			{ label: __("Distance"), field: "distance", format: fmt_km },
			{ label: __("Average Speed"), field: "averageSpeed", format: fmt_speed },
			{ label: __("Maximum Speed"), field: "maxSpeed", format: fmt_speed },
			{ label: __("Fuel Spent"), field: "spentFuel", format: (v) => (v != null ? `${v.toFixed(1)} L` : "—") },
			{ label: __("Engine Hours"), field: "engineHours", format: (v) => (v ?? "—") },
		],
		kpi: (rows) => {
			const total_distance = rows.reduce((s, r) => s + (r.distance || 0), 0);
			const total_fuel = rows.reduce((s, r) => s + (r.spentFuel || 0), 0);
			const avg_speed = rows.reduce((s, r) => s + (r.averageSpeed || 0), 0) / rows.length;
			const total_engine_hours = rows.reduce((s, r) => s + (r.engineHours || 0), 0);
			return [
				{ label: __("Total Distance"), value: fmt_km(total_distance) },
				{ label: __("Total Fuel"), value: `${total_fuel.toFixed(1)} L` },
				{ label: __("Avg Speed"), value: fmt_speed(avg_speed) },
				{ label: __("Total Engine Hours"), value: total_engine_hours },
			];
		},
	},
};

class ReportsHubPage {
	constructor(page) {
		this.page = page;
		this.active = "trips";
		this.instances = {};

		this.$body = $(`
			<div class="tracking_reports-hub">
				<ul class="nav nav-tabs mb-3 erp-tracking-report-tabs"></ul>
				<div class="erp-tracking-report-panels"></div>
			</div>
		`).appendTo(page.body);

		this.$tabs = this.$body.find(".erp-tracking-report-tabs");
		this.$panels = this.$body.find(".erp-tracking-report-panels");

		Object.keys(TAB_CONFIG).forEach((key) => {
			this.$tabs.append(`
				<li class="nav-item">
					<a class="nav-link ${key === this.active ? "active" : ""}" data-key="${key}" href="#">${TAB_CONFIG[key].label}</a>
				</li>
			`);
			this.$panels.append(`<div class="erp-tracking-report-panel" data-key="${key}" style="display:${key === this.active ? "block" : "none"};"></div>`);
		});

		this.$tabs.find("a").on("click", (e) => {
			e.preventDefault();
			const key = $(e.currentTarget).data("key");
			this._switch(key);
		});

		this._init_panel(this.active);
	}

	_switch(key) {
		this.active = key;
		this.$tabs.find("a").removeClass("active");
		this.$tabs.find(`a[data-key="${key}"]`).addClass("active");
		this.$panels.find(".erp-tracking-report-panel").hide();
		this.$panels.find(`.erp-tracking-report-panel[data-key="${key}"]`).show();
		this._init_panel(key);
	}

	_init_panel(key) {
		if (this.instances[key]) return; // build once, reuse on tab switch
		const cfg = TAB_CONFIG[key];
		const $panel = this.$panels.find(`.erp-tracking-report-panel[data-key="${key}"]`);
		this.instances[key] = new erp_tracking.ReportPage({
			wrapper: $panel,
			report_key: key,
			columns: cfg.columns,
			supports_daily: !!cfg.supports_daily,
			kpi: cfg.kpi || null,
		});
	}
}
