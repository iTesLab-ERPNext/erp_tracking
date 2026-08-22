// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-audit"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Audit Logs"),
		single_column: true,
	});

	new AuditPage(page);
};

class AuditPage {
	constructor(page) {
		this.page = page;
		this.$body = $(`<div class="erp-tracking-audit"></div>`).appendTo(page.body);
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
			<div class="erp-tracking-audit-table"></div>
		`);

		this.$from = this.$body.find(".erp-tracking-from");
		this.$to = this.$body.find(".erp-tracking-to");
		this.$table = this.$body.find(".erp-tracking-audit-table");

		const from = frappe.datetime.add_days(frappe.datetime.now_datetime(), -1);
		const to = frappe.datetime.now_datetime();
		this.$from.val(frappe.datetime.convert_to_system_tz(from, true));
		this.$to.val(frappe.datetime.convert_to_system_tz(to, true));

		this.$body.find(".erp-tracking-generate").on("click", () => this.generate());
		this.generate();
	}

	generate() {
		this.$table.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

		frappe.call({
			method: "erp_tracking.api.get_audit_log",
			args: { from_date: this.$from.val(), to_date: this.$to.val() },
			callback: (r) => {
				const result = r.message || {};
				if (!result.success) {
					const is_config = result.error === "TraccarConfigurationError";
					this.$table.html(`
						<div class="text-center text-muted p-4">
							<div style="font-size:1.5em;">${is_config ? "⚪" : "🔴"}</div>
							<div>${frappe.utils.escape_html(is_config ? __("Traccar is not configured.") : (result.message || __("Unable to load audit log.")))}</div>
						</div>
					`);
					return;
				}
				this._render_table(result.data || []);
			},
		});
	}

	_render_table(rows) {
		if (!rows.length) {
			this.$table.html(`<div class="text-muted text-center p-4">${__("No actions in this range.")}</div>`);
			return;
		}

		const table_rows = rows
			.map(
				(a) => `
					<tr>
						<td>${a.actionTime ? frappe.datetime.str_to_user(a.actionTime) : "—"}</td>
						<td>${frappe.utils.escape_html(a.userEmail || String(a.userId ?? "—"))}</td>
						<td>${frappe.utils.escape_html(a.actionType || "—")}</td>
						<td>${frappe.utils.escape_html(a.objectType || "—")}${a.objectId ? ` #${a.objectId}` : ""}</td>
						<td>${a.attributes && Object.keys(a.attributes).length ? `<code>${frappe.utils.escape_html(JSON.stringify(a.attributes))}</code>` : "—"}</td>
					</tr>
				`
			)
			.join("");

		this.$table.html(`
			<div class="text-muted small mb-2">${__("{0} actions", [rows.length])}</div>
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead>
						<tr><th>${__("Date")}</th><th>${__("User")}</th><th>${__("Action")}</th><th>${__("Object")}</th><th>${__("Details")}</th></tr>
					</thead>
					<tbody>${table_rows}</tbody>
				</table>
			</div>
		`);
	}
}
