// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// Chart.js is lazy-loaded from cdnjs only on this page, mirroring the
// Leaflet lazy-load pattern used by the Route page (Phase 3) - no other
// page in the app pulls in a charting library.

const CHARTJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js";

function ensure_chartjs(callback) {
	if (window.Chart) {
		callback();
		return;
	}
	frappe.require(CHARTJS_URL, callback);
}

frappe.pages["erp-tracking-statistics"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Server Statistics"),
		single_column: true,
	});

	new StatisticsPage(page);
};

class StatisticsPage {
	constructor(page) {
		this.page = page;
		this.chart = null;
		this.$body = $(`<div class="erp-tracking-statistics"></div>`).appendTo(page.body);
		this._render_shell();
	}

	_render_shell() {
		this.$body.html(`
			<div class="d-flex flex-wrap align-items-end mb-3" style="gap: 8px;">
				<div>
					<label class="text-muted small d-block">${__("From")}</label>
					<input type="datetime-local" class="form-control erp-tracking-from">
				</div>
				<div>
					<label class="text-muted small d-block">${__("To")}</label>
					<input type="datetime-local" class="form-control erp-tracking-to">
				</div>
				<button class="btn btn-primary erp-tracking-generate">${__("Generate")}</button>
			</div>
			<div class="erp-tracking-stats-chart mb-4" style="max-height: 320px;">
				<canvas class="erp-tracking-chart-canvas"></canvas>
			</div>
			<div class="erp-tracking-stats-table"></div>
		`);

		this.$from = this.$body.find(".erp-tracking-from");
		this.$to = this.$body.find(".erp-tracking-to");
		this.$table = this.$body.find(".erp-tracking-stats-table");
		this.$canvas = this.$body.find(".erp-tracking-chart-canvas");

		const from = frappe.datetime.add_days(frappe.datetime.now_datetime(), -7);
		const to = frappe.datetime.now_datetime();
		this.$from.val(frappe.datetime.convert_to_system_tz(from, true));
		this.$to.val(frappe.datetime.convert_to_system_tz(to, true));

		this.$body.find(".erp-tracking-generate").on("click", () => this.generate());
		this.generate();
	}

	generate() {
		this.$table.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

		frappe.call({
			method: "erp_tracking.api.get_statistics",
			args: { from_date: this.$from.val(), to_date: this.$to.val() },
			callback: (r) => {
				const result = r.message || {};
				if (!result.success) {
					const is_config = result.error === "TraccarConfigurationError";
					this.$table.html(`
						<div class="text-center text-muted p-4">
							<div style="font-size:1.5em;">${is_config ? "⚪" : "🔴"}</div>
							<div>${frappe.utils.escape_html(is_config ? __("Traccar is not configured.") : (result.message || __("Unable to load statistics.")))}</div>
						</div>
					`);
					return;
				}
				this.rows = result.data || [];
				this._render_table();
				ensure_chartjs(() => this._render_chart());
			},
		});
	}

	_render_table() {
		if (!this.rows.length) {
			this.$table.html(`<div class="text-muted text-center p-4">${__("No statistics for this range.")}</div>`);
			return;
		}

		const rows = this.rows
			.map(
				(s) => `
					<tr>
						<td>${s.captureTime ? frappe.datetime.str_to_user(s.captureTime) : "—"}</td>
						<td>${s.activeUsers ?? "—"}</td>
						<td>${s.activeDevices ?? "—"}</td>
						<td>${s.requests ?? "—"}</td>
						<td>${s.messagesReceived ?? "—"}</td>
						<td>${s.messagesStored ?? "—"}</td>
					</tr>
				`
			)
			.join("");

		this.$table.html(`
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead>
						<tr>
							<th>${__("Capture Time")}</th><th>${__("Active Users")}</th><th>${__("Active Devices")}</th>
							<th>${__("Requests")}</th><th>${__("Messages Received")}</th><th>${__("Messages Stored")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		`);
	}

	_render_chart() {
		if (this.chart) {
			this.chart.destroy();
		}
		if (!this.rows.length) return;

		const labels = this.rows.map((s) => (s.captureTime ? frappe.datetime.str_to_user(s.captureTime) : ""));

		this.chart = new Chart(this.$canvas[0], {
			type: "line",
			data: {
				labels,
				datasets: [
					{ label: __("Active Devices"), data: this.rows.map((s) => s.activeDevices || 0), borderColor: "#2490EF", tension: 0.2 },
					{ label: __("Messages Received"), data: this.rows.map((s) => s.messagesReceived || 0), borderColor: "#28A745", tension: 0.2 },
					{ label: __("Requests"), data: this.rows.map((s) => s.requests || 0), borderColor: "#F5A623", tension: 0.2 },
				],
			},
			options: { responsive: true, maintainAspectRatio: false },
		});
	}
}
