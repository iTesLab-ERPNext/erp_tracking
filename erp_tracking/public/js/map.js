/**
 * Leaflet loader and map helpers.
 *
 * The library and tile URLs come from Traccar Settings so an air-gapped site can
 * point them at self-hosted assets.
 */
frappe.provide("erp_tracking");

erp_tracking.map = {
	_loading: null,

	async load_library() {
		if (window.L) return window.L;
		if (this._loading) return this._loading;

		const config = await erp_tracking.get_config();
		this._loading = new Promise((resolve, reject) => {
			if (!config.leaflet_js_url) {
				reject(new Error("missing-map-library"));
				return;
			}
			if (config.leaflet_css_url) {
				$("<link>").attr({ rel: "stylesheet", href: config.leaflet_css_url }).appendTo("head");
			}
			const script = document.createElement("script");
			script.src = config.leaflet_js_url;
			script.onload = () => resolve(window.L);
			script.onerror = () => reject(new Error("map-library-unavailable"));
			document.head.appendChild(script);
		});
		return this._loading;
	},

	async render(container, { points = [], track = null, fit = true } = {}) {
		let L;
		try {
			L = await this.load_library();
		} catch (error) {
			$(container).html(
				erp_tracking.empty_state({
					title: __("Map unavailable"),
					message: __("The map library could not be loaded. Check the Leaflet URLs in Traccar Settings."),
				})
			);
			return null;
		}

		const config = await erp_tracking.get_config();
		$(container).empty().addClass("erpt-map");

		const map = L.map(container).setView([0, 0], 2);
		L.tileLayer(config.map_tile_url || "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
			attribution: config.map_attribution || "",
			maxZoom: 19,
		}).addTo(map);

		const markers = [];
		points.forEach((point) => {
			if (point.latitude === null || point.longitude === null) return;
			const marker = L.marker([point.latitude, point.longitude]).addTo(map);
			marker.bindPopup(this.popup(point));
			markers.push(marker);
		});

		let line = null;
		if (track && track.length > 1) {
			line = L.polyline(track, { color: "#2490EF", weight: 3 }).addTo(map);
		}

		if (fit) {
			if (line) map.fitBounds(line.getBounds(), { padding: [24, 24] });
			else if (markers.length) map.fitBounds(L.featureGroup(markers).getBounds(), { padding: [24, 24] });
		}

		setTimeout(() => map.invalidateSize(), 200);
		return map;
	},

	popup(point) {
		const rows = [
			[__("Device"), point.deviceName],
			[__("Time"), erp_tracking.format.datetime(point.fixTime || point.deviceTime)],
			[__("Speed"), erp_tracking.format.speed(point.speed)],
			[__("Address"), point.address],
		];
		return rows
			.filter(([, value]) => value)
			.map(([label, value]) => `<div><b>${label}:</b> ${frappe.utils.escape_html(String(value))}</div>`)
			.join("");
	},

	/** Open a single position on a map inside a dialog. */
	show_point(point) {
		const dialog = new frappe.ui.Dialog({
			title: point.deviceName || __("Position"),
			size: "large",
			fields: [{ fieldtype: "HTML", fieldname: "map" }],
		});
		dialog.show();
		const wrapper = dialog.fields_dict.map.$wrapper.css({ height: "420px" });
		this.render(wrapper.get(0), { points: [point] });
	},
};
