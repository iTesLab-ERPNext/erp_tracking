// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// Route needs an actual polyline map, so this page lazy-loads Leaflet from
// cdnjs (already an allowed CDN for this environment) only when the page is
// opened - no other page in the app pulls in a mapping library.

frappe.pages["tracking_route"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Route"),
		single_column: true,
	});

	new RoutePage(page);
};

const LEAFLET_CSS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css";
const LEAFLET_JS = "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js";

function ensure_leaflet(callback) {
	if (window.L) {
		callback();
		return;
	}
	if (!document.querySelector(`link[href="${LEAFLET_CSS}"]`)) {
		$("<link>").attr({ rel: "stylesheet", href: LEAFLET_CSS }).appendTo("head");
	}
	frappe.require(LEAFLET_JS, callback);
}

class RoutePage {
	constructor(page) {
		this.page = page;
		this.map = null;
		this.$body = $(`<div class="tracking_route"></div>`).appendTo(page.body);
		this._render_shell();
		this._load_reference_data();
	}

	_render_shell() {
		this.$body.html(`
			<div class="d-flex flex-wrap align-items-end mb-3" style="gap: 8px;">
				<div>
					<label class="text-muted small d-block">${__("Devices")}</label>
					<select class="form-control erp-tracking-device-select" multiple style="min-width: 220px; height: 70px;"></select>
				</div>
				<div>
					<label class="text-muted small d-block">${__("Groups")}</label>
					<select class="form-control erp-tracking-group-select" multiple style="min-width: 220px; height: 70px;"></select>
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
			</div>
			<div class="tracking_route-map mb-3" style="height: 420px; border: 1px solid var(--border-color); border-radius: 6px;"></div>
			<div class="tracking_route-table"></div>
		`);

		this.$deviceSelect = this.$body.find(".erp-tracking-device-select");
		this.$groupSelect = this.$body.find(".erp-tracking-group-select");
		this.$from = this.$body.find(".erp-tracking-from");
		this.$to = this.$body.find(".erp-tracking-to");
		this.$mapEl = this.$body.find(".tracking_route-map");
		this.$table = this.$body.find(".tracking_route-table");

		const from = frappe.datetime.add_days(frappe.datetime.now_datetime(), -1);
		const to = frappe.datetime.now_datetime();
		this.$from.val(frappe.datetime.convert_to_system_tz(from, true));
		this.$to.val(frappe.datetime.convert_to_system_tz(to, true));

		this.$body.find(".erp-tracking-generate").on("click", () => this.generate());
	}

	_load_reference_data() {
		frappe.call({
			method: "erp_tracking.api.get_devices",
			args: { limit: 500 },
			callback: (r) => {
				const result = r.message || {};
				if (result.success) {
					(result.data || []).forEach((d) =>
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
					(result.data || []).forEach((g) =>
						this.$groupSelect.append(`<option value="${g.id}">${frappe.utils.escape_html(g.name)}</option>`)
					);
				}
			},
		});
	}

	generate() {
		const device_ids = (this.$deviceSelect.val() || []).map(Number);
		const group_ids = (this.$groupSelect.val() || []).map(Number);

		if (!device_ids.length && !group_ids.length) {
			frappe.msgprint(__("Please select at least one device or group."));
			return;
		}

		this.$table.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);

		frappe.call({
			method: "erp_tracking.api.get_route",
			args: {
				device_ids: JSON.stringify(device_ids),
				group_ids: JSON.stringify(group_ids),
				from_date: this.$from.val(),
				to_date: this.$to.val(),
			},
			callback: (r) => {
				const result = r.message || {};
				if (!result.success) {
					const is_config = result.error === "TraccarConfigurationError";
					this.$table.html(`
						<div class="text-center text-muted p-4">
							<div style="font-size:1.5em;">${is_config ? "⚪" : "🔴"}</div>
							<div>${frappe.utils.escape_html(is_config ? __("Traccar is not configured.") : (result.message || __("Unable to load route.")))}</div>
						</div>
					`);
					return;
				}
				this.positions = result.data || [];
				this._render_table();
				ensure_leaflet(() => this._render_map());
			},
		});
	}

	_render_map() {
		const points = (this.positions || []).map((p) => [p.latitude, p.longitude]);

		if (!this.map) {
			this.map = L.map(this.$mapEl[0]);
			L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
				attribution: "&copy; OpenStreetMap contributors",
				maxZoom: 19,
			}).addTo(this.map);
		}
		if (this.polyline) this.map.removeLayer(this.polyline);
		if (this.markers) this.markers.forEach((m) => this.map.removeLayer(m));

		if (!points.length) {
			this.map.setView([0, 0], 2);
			return;
		}

		this.polyline = L.polyline(points, { color: "#2490EF", weight: 3 }).addTo(this.map);
		this.markers = [
			L.marker(points[0]).addTo(this.map).bindPopup(__("Start")),
			L.marker(points[points.length - 1]).addTo(this.map).bindPopup(__("End")),
		];
		this.map.fitBounds(this.polyline.getBounds(), { padding: [20, 20] });
	}

	_render_table() {
		if (!this.positions.length) {
			this.$table.html(`<div class="text-muted text-center p-4">${__("No positions found for this range.")}</div>`);
			return;
		}

		const rows = this.positions
			.map(
				(p) => `
					<tr>
						<td>${p.fixTime ? frappe.datetime.str_to_user(p.fixTime) : "—"}</td>
						<td>${(p.latitude ?? 0).toFixed(5)}</td>
						<td>${(p.longitude ?? 0).toFixed(5)}</td>
						<td>${(p.speed ?? 0).toFixed(1)} kn</td>
						<td>${(p.course ?? 0).toFixed(0)}°</td>
						<td>${frappe.utils.escape_html(p.address || "—")}</td>
					</tr>
				`
			)
			.join("");

		this.$table.html(`
			<div class="text-muted small mb-2">${__("{0} positions", [this.positions.length])}</div>
			<div class="table-responsive">
				<table class="table table-bordered table-hover">
					<thead>
						<tr><th>${__("Time")}</th><th>${__("Latitude")}</th><th>${__("Longitude")}</th><th>${__("Speed")}</th><th>${__("Course")}</th><th>${__("Address")}</th></tr>
					</thead>
					<tbody>${rows}</tbody>
				</table>
			</div>
		`);
	}
}
