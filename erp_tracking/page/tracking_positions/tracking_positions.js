// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// Live Positions needs to join positions with device metadata (name, group)
// for filtering and display, which the generic ListEngine doesn't do, so
// this page renders itself rather than configuring erp_tracking.ListEngine.
// It still reuses erp_tracking.status_badge for consistency.

frappe.pages["erp-tracking-positions"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Live Positions"),
		single_column: true,
	});

	new LivePositionsPage(page);
};

const PAGE_LENGTH = 20;

class LivePositionsPage {
	constructor(page) {
		this.page = page;
		this.devices = [];
		this.groups = [];
		this.offset = 0;
		this.filters = { device_id: null, group_id: null, status: null };

		this.page.set_primary_action(__("Refresh"), () => this.load_positions(true), "fa fa-refresh");

		this.$body = $(`<div class="erp-tracking-positions"></div>`).appendTo(page.body);
		this._render_shell();
		this._load_reference_data();
	}

	_render_shell() {
		this.$body.html(`
			<div class="d-flex flex-wrap mb-3" style="gap: 8px;">
				<select class="form-control erp-tracking-device-filter" style="max-width: 220px;">
					<option value="">${__("All Devices")}</option>
				</select>
				<select class="form-control erp-tracking-group-filter" style="max-width: 220px;">
					<option value="">${__("All Groups")}</option>
				</select>
				<select class="form-control erp-tracking-status-filter" style="max-width: 160px;">
					<option value="">${__("All Statuses")}</option>
					<option value="online">${__("Online")}</option>
					<option value="offline">${__("Offline")}</option>
					<option value="unknown">${__("Unknown")}</option>
				</select>
			</div>
			<div class="erp-tracking-positions-body"></div>
			<div class="d-flex align-items-center justify-content-between mt-3">
				<button class="btn btn-default btn-sm erp-tracking-prev">
					<i class="fa fa-angle-left"></i> ${__("Previous")}
				</button>
				<span class="text-muted small erp-tracking-page-label"></span>
				<button class="btn btn-default btn-sm erp-tracking-next">
					${__("Next")} <i class="fa fa-angle-right"></i>
				</button>
			</div>
		`);

		this.$listBody = this.$body.find(".erp-tracking-positions-body");
		this.$pageLabel = this.$body.find(".erp-tracking-page-label");

		this.$body.find(".erp-tracking-device-filter").on("change", (e) => {
			this.filters.device_id = $(e.currentTarget).val() || null;
			this.offset = 0;
			this._render_table();
		});
		this.$body.find(".erp-tracking-group-filter").on("change", (e) => {
			this.filters.group_id = $(e.currentTarget).val() || null;
			this.offset = 0;
			this._render_table();
		});
		this.$body.find(".erp-tracking-status-filter").on("change", (e) => {
			this.filters.status = $(e.currentTarget).val() || null;
			this.offset = 0;
			this._render_table();
		});
		this.$body.find(".erp-tracking-prev").on("click", () => {
			if (this.offset === 0) return;
			this.offset = Math.max(0, this.offset - PAGE_LENGTH);
			this._render_table();
		});
		this.$body.find(".erp-tracking-next").on("click", () => {
			this.offset += PAGE_LENGTH;
			this._render_table();
		});
	}

	_load_reference_data() {
		frappe.call({
			method: "erp_tracking.api.get_devices",
			args: { limit: 500 },
			callback: (r) => {
				const result = r.message || {};
				if (result.success) {
					this.devices = result.data || [];
					const $sel = this.$body.find(".erp-tracking-device-filter");
					this.devices.forEach((d) => $sel.append(`<option value="${d.id}">${frappe.utils.escape_html(d.name)}</option>`));
				}
				this._load_groups();
			},
		});
	}

	_load_groups() {
		frappe.call({
			method: "erp_tracking.api.get_groups",
			args: { limit: 200 },
			callback: (r) => {
				const result = r.message || {};
				if (result.success) {
					this.groups = result.data || [];
					const $sel = this.$body.find(".erp-tracking-group-filter");
					this.groups.forEach((g) => $sel.append(`<option value="${g.id}">${frappe.utils.escape_html(g.name)}</option>`));
				}
				this.load_positions();
			},
		});
	}

	_device_by_id(id) {
		return this.devices.find((d) => d.id === id);
	}

	load_positions(refresh = false) {
		this.$listBody.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

		frappe.call({
			method: "erp_tracking.api.get_live_positions",
			args: { refresh: refresh ? 1 : 0 },
			callback: (r) => {
				const result = r.message || {};
				if (!result.success) {
					this._render_error(result);
					return;
				}
				this.positions = result.data || [];
				this._render_table();
			},
		});
	}

	_filtered_positions() {
		return (this.positions || []).filter((p) => {
			const device = this._device_by_id(p.deviceId);
			if (this.filters.device_id && String(p.deviceId) !== String(this.filters.device_id)) return false;
			if (this.filters.group_id && (!device || String(device.groupId) !== String(this.filters.group_id))) return false;
			if (this.filters.status && (!device || device.status !== this.filters.status)) return false;
			return true;
		});
	}

	_render_error(result) {
		const is_config = result.error === "TraccarConfigurationError";
		this.$listBody.html(`
			<div class="text-center text-muted p-4">
				<div style="font-size:1.5em;">${is_config ? "⚪" : "🔴"}</div>
				<div>${frappe.utils.escape_html(is_config ? __("Traccar is not configured.") : (result.message || __("Unable to load positions.")))}</div>
			</div>
		`);
	}

	_render_table() {
		const filtered = this._filtered_positions();
		const page_rows = filtered.slice(this.offset, this.offset + PAGE_LENGTH);

		if (!filtered.length) {
			this.$listBody.html(`<div class="text-muted text-center p-4">${__("No positions found.")}</div>`);
			this.$pageLabel.text("");
			return;
		}

		const header = [__("Device"), __("Time"), __("Latitude"), __("Longitude"), __("Speed"), __("Course"), __("Altitude"), __("Accuracy"), __("Address"), __("Map")]
			.map((h) => `<th>${h}</th>`)
			.join("");

		const body = page_rows
			.map((p) => {
				const device = this._device_by_id(p.deviceId);
				const device_name = device ? frappe.utils.escape_html(device.name) : `#${p.deviceId}`;
				const time = p.fixTime ? frappe.datetime.prettyDate(p.fixTime) : "—";
				const map_link = `https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}#map=16/${p.latitude}/${p.longitude}`;
				return `
					<tr>
						<td>${device_name}</td>
						<td>${time}</td>
						<td>${(p.latitude ?? 0).toFixed(5)}</td>
						<td>${(p.longitude ?? 0).toFixed(5)}</td>
						<td>${(p.speed ?? 0).toFixed(1)} kn</td>
						<td>${(p.course ?? 0).toFixed(0)}°</td>
						<td>${p.altitude != null ? p.altitude.toFixed(0) + " m" : "—"}</td>
						<td>${p.accuracy != null ? p.accuracy.toFixed(0) + " m" : "—"}</td>
						<td>${frappe.utils.escape_html(p.address || "—")}</td>
						<td><a href="${map_link}" target="_blank" rel="noopener"><i class="fa fa-map-marker"></i> ${__("View")}</a></td>
					</tr>
				`;
			})
			.join("");

		this.$listBody.html(`
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead><tr>${header}</tr></thead>
					<tbody>${body}</tbody>
				</table>
			</div>
		`);

		this.$pageLabel.text(__("Showing {0}-{1} of {2}", [this.offset + 1, Math.min(this.offset + PAGE_LENGTH, filtered.length), filtered.length]));
	}
}
