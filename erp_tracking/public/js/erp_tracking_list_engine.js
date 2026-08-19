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
