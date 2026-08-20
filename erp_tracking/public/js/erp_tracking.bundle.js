// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// Generic list engine (Section 38). Devices/Groups/Users pages (and Drivers,
// Maintenance, Notifications, Commands, Orders in later phases) all
// configure one of these instead of re-implementing search/pagination/
// sorting/refresh from scratch.
//
// Usage:
//   const list = new erp_tracking.ListEngine({
//     wrapper: $(el),
//     method: "erp_tracking.api.get_devices",
//     page_length: 20,
//     columns: [
//       { label: __("Name"), field: "name" },
//       { label: __("Status"), field: "status", format: (v) => badge(v) },
//     ],
//     on_row_click: (row) => { ... },
//   });
//   list.load();

frappe.provide("erp_tracking");

erp_tracking.ListEngine = class ListEngine {
	constructor(opts) {
		this.wrapper = opts.wrapper;
		this.method = opts.method;
		this.columns = opts.columns || [];
		this.page_length = opts.page_length || 20;
		this.on_row_click = opts.on_row_click || null;
		this.extra_args = opts.extra_args || {};
		this.offset = 0;
		this.keyword = "";
		this.rows = [];

		this._render_shell();
	}

	_render_shell() {
		this.wrapper.empty().append(`
			<div class="erp-tracking-list">
				<div class="erp-tracking-list-toolbar d-flex align-items-center mb-3" style="gap: 8px;">
					<input type="text" class="form-control erp-tracking-search"
						placeholder="${__("Search...")}" style="max-width: 260px;">
					<button class="btn btn-default btn-sm erp-tracking-refresh">
						<i class="fa fa-refresh"></i> ${__("Refresh")}
					</button>
					<div class="flex-grow-1"></div>
					<span class="text-muted small erp-tracking-count"></span>
				</div>
				<div class="erp-tracking-list-body"></div>
				<div class="erp-tracking-list-pagination d-flex align-items-center justify-content-between mt-3">
					<button class="btn btn-default btn-sm erp-tracking-prev">
						<i class="fa fa-angle-left"></i> ${__("Previous")}
					</button>
					<span class="text-muted small erp-tracking-page-label"></span>
					<button class="btn btn-default btn-sm erp-tracking-next">
						${__("Next")} <i class="fa fa-angle-right"></i>
					</button>
				</div>
			</div>
		`);

		this.$search = this.wrapper.find(".erp-tracking-search");
		this.$body = this.wrapper.find(".erp-tracking-list-body");
		this.$count = this.wrapper.find(".erp-tracking-count");
		this.$page_label = this.wrapper.find(".erp-tracking-page-label");

		let search_timeout;
		this.$search.on("input", () => {
			clearTimeout(search_timeout);
			search_timeout = setTimeout(() => {
				this.keyword = this.$search.val();
				this.offset = 0;
				this.load();
			}, 300);
		});

		this.wrapper.find(".erp-tracking-refresh").on("click", () => this.load({ refresh: true }));
		this.wrapper.find(".erp-tracking-prev").on("click", () => {
			if (this.offset === 0) return;
			this.offset = Math.max(0, this.offset - this.page_length);
			this.load();
		});
		this.wrapper.find(".erp-tracking-next").on("click", () => {
			if (this.rows.length < this.page_length) return; // heuristic: short page = last page
			this.offset += this.page_length;
			this.load();
		});
	}

	load(opts = {}) {
		this.$body.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

		frappe.call({
			method: this.method,
			args: Object.assign(
				{
					keyword: this.keyword || undefined,
					limit: this.page_length,
					offset: this.offset,
					refresh: opts.refresh ? 1 : 0,
				},
				this.extra_args
			),
			callback: (r) => {
				const result = r.message || {};
				this._render_result(result);
			},
			error: () => {
				this._render_error({ message: __("Unable to reach the server.") });
			},
		});
	}

	_render_result(result) {
		if (!result.success) {
			this._render_error(result);
			return;
		}

		this.rows = result.data || [];
		this._render_table();
		this.$page_label.text(
			__("Showing {0}-{1}", [this.offset + 1, this.offset + this.rows.length])
		);
		this.$count.text(this.rows.length === this.page_length ? __("{0}+ records", [this.rows.length]) : __("{0} records", [this.rows.length]));
	}

	_render_error(result) {
		// Section 49: never substitute fake data. Show the real error/empty state.
		const is_config_error = result.error === "TraccarConfigurationError";
		const message = is_config_error
			? __("Traccar is not configured.")
			: result.message || __("Unable to load data from Traccar.");

		this.$body.html(`
			<div class="text-center text-muted p-4">
				<div style="font-size: 1.5em;">${is_config_error ? "⚪" : "🔴"}</div>
				<div>${frappe.utils.escape_html(message)}</div>
			</div>
		`);
		this.$count.text("");
		this.$page_label.text("");
	}

	_render_table() {
		if (!this.rows.length) {
			this.$body.html(`<div class="text-muted text-center p-4">${__("No records found.")}</div>`);
			return;
		}

		const header = this.columns
			.map((c) => `<th>${frappe.utils.escape_html(c.label)}</th>`)
			.join("");

		const body = this.rows
			.map((row, idx) => {
				const cells = this.columns
					.map((c) => {
						const raw = row[c.field];
						const value = c.format ? c.format(raw, row) : frappe.utils.escape_html(raw ?? "");
						return `<td>${value}</td>`;
					})
					.join("");
				return `<tr class="erp-tracking-row" data-idx="${idx}" style="cursor:${this.on_row_click ? "pointer" : "default"}">${cells}</tr>`;
			})
			.join("");

		this.$body.html(`
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead><tr>${header}</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`);

		if (this.on_row_click) {
			this.$body.find(".erp-tracking-row").on("click", (e) => {
				const idx = $(e.currentTarget).data("idx");
				this.on_row_click(this.rows[idx]);
			});
		}
	}
};

// Small shared badge helper reused by every page for device/connection status.
erp_tracking.status_badge = function (status) {
	const map = {
		online: { emoji: "🟢", cls: "success" },
		offline: { emoji: "🔴", cls: "danger" },
		unknown: { emoji: "🟠", cls: "warning" },
	};
	const meta = map[status] || { emoji: "⚪", cls: "secondary" };
	return `<span class="indicator-pill ${meta.cls}">${meta.emoji} ${frappe.utils.escape_html(status || "unknown")}</span>`;
};

// -----------------------------------------------------------------------------
// Generic report engine UI (Section 37) — Trips, Stops, Summary, Events all
// configure one of these instead of each page hand-rolling filters, a
// table, and export buttons. Mirrors the server-side REPORT_CONFIG in
// reports.py: same filters, same two export types (xlsx / mail — the spec
// has no CSV or PDF export operation for these reports, see reports.py).
erp_tracking.ReportPage = class ReportPage {
	constructor(opts) {
		this.wrapper = opts.wrapper;
		this.report_key = opts.report_key; // "trips" | "stops" | "summary" | "events"
		this.columns = opts.columns; // [{label, field, format}]
		this.supports_daily = !!opts.supports_daily;
		this.supports_event_types = !!opts.supports_event_types;
		this.kpi = opts.kpi || null; // (rows) => [{label, value}]
		this.devices = [];
		this.groups = [];
		this.rows = [];

		this._render_shell();
		this._load_reference_data();
	}

	_render_shell() {
		this.wrapper.html(`
			<div class="d-flex flex-wrap align-items-end mb-3" style="gap: 8px;">
				<div>
					<label class="text-muted small d-block">${__("Devices")}</label>
					<select class="form-control erp-tracking-device-select" multiple style="min-width: 200px; height: 70px;"></select>
				</div>
				<div>
					<label class="text-muted small d-block">${__("Groups")}</label>
					<select class="form-control erp-tracking-group-select" multiple style="min-width: 200px; height: 70px;"></select>
				</div>
				<div>
					<label class="text-muted small d-block">${__("From")}</label>
					<input type="datetime-local" class="form-control erp-tracking-from">
				</div>
				<div>
					<label class="text-muted small d-block">${__("To")}</label>
					<input type="datetime-local" class="form-control erp-tracking-to">
				</div>
				${
					this.supports_event_types
						? `<div>
							<label class="text-muted small d-block">${__("Event Types")}</label>
							<input type="text" class="form-control erp-tracking-event-types" style="min-width: 200px;"
								placeholder="${__("comma-separated, blank = all")}">
						</div>`
						: ""
				}
				${
					this.supports_daily
						? `<div class="form-check" style="margin-bottom: 6px;">
							<input type="checkbox" class="form-check-input erp-tracking-daily" id="erp-tracking-daily">
							<label class="form-check-label" for="erp-tracking-daily">${__("Daily breakdown")}</label>
						</div>`
						: ""
				}
				<button class="btn btn-primary erp-tracking-generate">${__("Generate")}</button>
				<button class="btn btn-default erp-tracking-refresh" title="${__("Refresh")}"><i class="fa fa-refresh"></i></button>
				<div class="flex-grow-1"></div>
				<div class="btn-group erp-tracking-export-group" style="display:none;">
					<button class="btn btn-default btn-sm erp-tracking-export-xlsx">${__("Export XLSX")}</button>
					<button class="btn btn-default btn-sm erp-tracking-export-mail">${__("Email Report")}</button>
				</div>
			</div>
			<div class="erp-tracking-report-kpis mb-3" style="display:none;"></div>
			<div class="erp-tracking-report-body"></div>
		`);

		this.$deviceSelect = this.wrapper.find(".erp-tracking-device-select");
		this.$groupSelect = this.wrapper.find(".erp-tracking-group-select");
		this.$from = this.wrapper.find(".erp-tracking-from");
		this.$to = this.wrapper.find(".erp-tracking-to");
		this.$eventTypes = this.wrapper.find(".erp-tracking-event-types");
		this.$daily = this.wrapper.find(".erp-tracking-daily");
		this.$body = this.wrapper.find(".erp-tracking-report-body");
		this.$kpis = this.wrapper.find(".erp-tracking-report-kpis");
		this.$exportGroup = this.wrapper.find(".erp-tracking-export-group");

		const from = frappe.datetime.add_days(frappe.datetime.now_datetime(), -7);
		const to = frappe.datetime.now_datetime();
		this.$from.val(frappe.datetime.convert_to_system_tz(from, true));
		this.$to.val(frappe.datetime.convert_to_system_tz(to, true));

		this.wrapper.find(".erp-tracking-generate").on("click", () => this.generate());
		this.wrapper.find(".erp-tracking-refresh").on("click", () => this.generate());
		this.wrapper.find(".erp-tracking-export-xlsx").on("click", () => this._download("xlsx"));
		this.wrapper.find(".erp-tracking-export-mail").on("click", () => this._download("mail"));
	}

	_load_reference_data() {
		frappe.call({
			method: "erp_tracking.api.get_devices",
			args: { limit: 500 },
			callback: (r) => {
				const result = r.message || {};
				if (result.success) {
					this.devices = result.data || [];
					this.devices.forEach((d) =>
						this.$deviceSelect.append(`<option value="${d.id}">${frappe.utils.escape_html(d.name)}</option>`)
					);
				}
			},
		});
		frappe.call({
			method: "erp_tracking.api.get_groups",
			args: { limit: 200 },
			callback: (r) => {
				const result = r.message || {};
				if (result.success) {
					this.groups = result.data || [];
					this.groups.forEach((g) =>
						this.$groupSelect.append(`<option value="${g.id}">${frappe.utils.escape_html(g.name)}</option>`)
					);
				}
			},
		});
	}

	_current_filters() {
		const device_ids = (this.$deviceSelect.val() || []).map(Number);
		const group_ids = (this.$groupSelect.val() || []).map(Number);
		const event_types = this.$eventTypes.length && this.$eventTypes.val()
			? this.$eventTypes.val().split(",").map((s) => s.trim()).filter(Boolean)
			: null;
		const daily = this.$daily.length ? this.$daily.is(":checked") : null;

		return {
			device_ids,
			group_ids,
			from_date: this.$from.val(),
			to_date: this.$to.val(),
			event_types,
			daily,
		};
	}

	generate() {
		const filters = this._current_filters();
		if (!filters.device_ids.length && !filters.group_ids.length) {
			frappe.msgprint(__("Please select at least one device or group."));
			return;
		}

		this.$body.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);
		this.$kpis.hide();
		this.$exportGroup.hide();

		frappe.call({
			method: "erp_tracking.api.get_report",
			args: {
				report_key: this.report_key,
				device_ids: JSON.stringify(filters.device_ids),
				group_ids: JSON.stringify(filters.group_ids),
				from_date: filters.from_date,
				to_date: filters.to_date,
				event_types: filters.event_types ? JSON.stringify(filters.event_types) : undefined,
				daily: filters.daily,
			},
			callback: (r) => {
				const result = r.message || {};
				if (!result.success) {
					const is_config = result.error === "TraccarConfigurationError";
					this.$body.html(`
						<div class="text-center text-muted p-4">
							<div style="font-size:1.5em;">${is_config ? "⚪" : "🔴"}</div>
							<div>${frappe.utils.escape_html(is_config ? __("Traccar is not configured.") : (result.message || __("Unable to generate report.")))}</div>
						</div>
					`);
					return;
				}
				this.rows = result.data || [];
				this._render_table();
				this._render_kpis();
				this.$exportGroup.toggle(this.rows.length > 0);
			},
		});
	}

	_render_kpis() {
		if (!this.kpi || !this.rows.length) {
			this.$kpis.hide();
			return;
		}
		const cards = this.kpi(this.rows);
		this.$kpis
			.html(
				cards
					.map(
						(c) => `
					<div class="d-inline-block card p-3 mr-2" style="min-width: 140px;">
						<div class="text-muted small">${c.label}</div>
						<div class="h4 mb-0">${c.value}</div>
					</div>
				`
					)
					.join("")
			)
			.show();
	}

	_render_table() {
		if (!this.rows.length) {
			this.$body.html(`<div class="text-muted text-center p-4">${__("No records found for this range.")}</div>`);
			return;
		}

		const header = this.columns.map((c) => `<th>${frappe.utils.escape_html(c.label)}</th>`).join("");
		const body = this.rows
			.map((row) => {
				const cells = this.columns
					.map((c) => {
						const raw = row[c.field];
						const value = c.format ? c.format(raw, row) : frappe.utils.escape_html(raw ?? "—");
						return `<td>${value}</td>`;
					})
					.join("");
				return `<tr>${cells}</tr>`;
			})
			.join("");

		this.$body.html(`
			<div class="text-muted small mb-2">${__("{0} records", [this.rows.length])}</div>
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead><tr>${header}</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`);
	}

	_download(download_type) {
		const filters = this._current_filters();
		const params = new URLSearchParams({
			report_key: this.report_key,
			download_type,
			device_ids: JSON.stringify(filters.device_ids),
			group_ids: JSON.stringify(filters.group_ids),
			from_date: filters.from_date,
			to_date: filters.to_date,
		});
		if (filters.event_types) params.set("event_types", JSON.stringify(filters.event_types));
		if (filters.daily !== null) params.set("daily", filters.daily ? "1" : "0");

		if (download_type === "mail") {
			frappe.call({
				method: "erp_tracking.api.download_report",
				args: Object.fromEntries(params),
				callback: () => frappe.show_alert({ message: __("Report queued for email delivery."), indicator: "green" }),
			});
			return;
		}

		window.open(`/api/method/erp_tracking.api.download_report?${params.toString()}`, "_blank");
	}
};

// Curated common Traccar event type identifiers, for the Events page's
// badge coloring only - the spec has no "list all event types" endpoint,
// so this is a display convenience, not fetched from the API (Section 50).
erp_tracking.event_badge = function (type) {
	const danger = ["deviceOffline", "geofenceExit", "alarm", "ignitionOff", "deviceOverspeed", "sos"];
	const success = ["deviceOnline", "geofenceEnter", "ignitionOn"];
	const cls = danger.includes(type) ? "danger" : success.includes(type) ? "success" : "blue";
	return `<span class="indicator-pill ${cls}">${frappe.utils.escape_html(type || "—")}</span>`;
};

