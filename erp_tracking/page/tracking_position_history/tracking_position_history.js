// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-position-history"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Position History"),
		single_column: true,
	});

	new PositionHistoryPage(page);
};

class PositionHistoryPage {
	constructor(page) {
		this.page = page;
		this.device_id = null;
		this.from_date = frappe.datetime.add_days(frappe.datetime.now_datetime(), -1);
		this.to_date = frappe.datetime.now_datetime();
		this.positions = [];

		this.$body = $(`<div class="erp-tracking-position-history"></div>`).appendTo(page.body);
		this._render_shell();
		this._load_devices();
	}

	_render_shell() {
		this.$body.html(`
			<div class="d-flex flex-wrap align-items-end mb-3" style="gap: 8px;">
				<div>
					<label class="text-muted small d-block">${__("Device")}</label>
					<select class="form-control erp-tracking-device-select" style="min-width: 200px;"></select>
				</div>
				<div>
					<label class="text-muted small d-block">${__("From")}</label>
					<input type="datetime-local" class="form-control erp-tracking-from">
				</div>
				<div>
					<label class="text-muted small d-block">${__("To")}</label>
					<input type="datetime-local" class="form-control erp-tracking-to">
				</div>
				<button class="btn btn-primary erp-tracking-generate">${__("Generate")}</button>
				<div class="flex-grow-1"></div>
				<div class="btn-group erp-tracking-export-group" style="display:none;">
					<button class="btn btn-default btn-sm erp-tracking-export-csv">${__("Export CSV")}</button>
					<button class="btn btn-default btn-sm erp-tracking-export-kml">${__("Export KML")}</button>
					<button class="btn btn-default btn-sm erp-tracking-export-gpx">${__("Export GPX")}</button>
				</div>
			</div>
			<div class="erp-tracking-history-body"></div>
		`);

		this.$deviceSelect = this.$body.find(".erp-tracking-device-select");
		this.$from = this.$body.find(".erp-tracking-from");
		this.$to = this.$body.find(".erp-tracking-to");
		this.$historyBody = this.$body.find(".erp-tracking-history-body");
		this.$exportGroup = this.$body.find(".erp-tracking-export-group");

		this.$from.val(frappe.datetime.convert_to_system_tz(this.from_date, true));
		this.$to.val(frappe.datetime.convert_to_system_tz(this.to_date, true));

		this.$body.find(".erp-tracking-generate").on("click", () => this.generate());
		this.$body.find(".erp-tracking-export-csv").on("click", () => this._download("csv"));
		this.$body.find(".erp-tracking-export-kml").on("click", () => this._download("kml"));
		this.$body.find(".erp-tracking-export-gpx").on("click", () => this._download("gpx"));
	}

	_load_devices() {
		frappe.call({
			method: "erp_tracking.api.get_devices",
			args: { limit: 500 },
			callback: (r) => {
				const result = r.message || {};
				if (result.success) {
					(result.data || []).forEach((d) => {
						this.$deviceSelect.append(`<option value="${d.id}">${frappe.utils.escape_html(d.name)}</option>`);
					});
				}
			},
		});
	}

	generate() {
		const device_id = this.$deviceSelect.val();
		if (!device_id) {
			frappe.msgprint(__("Please select a device."));
			return;
		}

		this.device_id = device_id;
		this.from_date = this.$from.val();
		this.to_date = this.$to.val();

		this.$historyBody.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);
		this.$exportGroup.hide();

		frappe.call({
			method: "erp_tracking.api.get_position_history",
			args: { device_id, from_date: this.from_date, to_date: this.to_date },
			callback: (r) => {
				const result = r.message || {};
				if (!result.success) {
					const is_config = result.error === "TraccarConfigurationError";
					this.$historyBody.html(`
						<div class="text-center text-muted p-4">
							<div style="font-size:1.5em;">${is_config ? "⚪" : "🔴"}</div>
							<div>${frappe.utils.escape_html(is_config ? __("Traccar is not configured.") : (result.message || __("Unable to load position history.")))}</div>
						</div>
					`);
					return;
				}
				this.positions = result.data || [];
				this._render_table();
				this.$exportGroup.toggle(this.positions.length > 0);
			},
		});
	}

	_render_table() {
		if (!this.positions.length) {
			this.$historyBody.html(`<div class="text-muted text-center p-4">${__("No positions found for this range.")}</div>`);
			return;
		}

		const rows = this.positions
			.map((p) => {
				const map_link = `https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}#map=16/${p.latitude}/${p.longitude}`;
				return `
					<tr>
						<td>${p.fixTime ? frappe.datetime.str_to_user(p.fixTime) : "—"}</td>
						<td>${(p.latitude ?? 0).toFixed(5)}</td>
						<td>${(p.longitude ?? 0).toFixed(5)}</td>
						<td>${(p.speed ?? 0).toFixed(1)} kn</td>
						<td>${(p.course ?? 0).toFixed(0)}°</td>
						<td>${p.altitude != null ? p.altitude.toFixed(0) + " m" : "—"}</td>
						<td>${p.accuracy != null ? p.accuracy.toFixed(0) + " m" : "—"}</td>
						<td><a href="${map_link}" target="_blank" rel="noopener"><i class="fa fa-map-marker"></i></a></td>
					</tr>
				`;
			})
			.join("");

		this.$historyBody.html(`
			<div class="text-muted small mb-2">${__("{0} positions", [this.positions.length])}</div>
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead>
						<tr>
							<th>${__("Time")}</th><th>${__("Latitude")}</th><th>${__("Longitude")}</th>
							<th>${__("Speed")}</th><th>${__("Course")}</th><th>${__("Altitude")}</th>
							<th>${__("Accuracy")}</th><th>${__("Map")}</th>
						</tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		`);
	}

	_download(format) {
		if (!this.device_id) return;
		const params = new URLSearchParams({
			device_id: this.device_id,
			from_date: this.from_date,
			to_date: this.to_date,
		});
		// Native Traccar export endpoints (Section 15/39) - triggered as a
		// direct navigation so the browser handles the file download.
		window.open(`/api/method/erp_tracking.api.download_positions_${format}?${params.toString()}`, "_blank");
	}
}
