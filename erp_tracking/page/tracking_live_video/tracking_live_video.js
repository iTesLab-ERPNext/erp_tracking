// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// The <video> element's source is always this app's own whitelisted
// get_stream_playlist endpoint, never a Traccar URL directly - see
// stream.py's module docstring for why (Section 35 "don't proxy video"
// vs Section 41 "never expose tokens to the frontend"; the token-based
// workaround Traccar itself documents for browser players is exactly what
// Section 41 forbids, so this app proxies instead).
//
// hls.js is lazy-loaded from cdnjs only on this page, mirroring the
// Leaflet/Chart.js lazy-load pattern used on Route and Statistics.

const HLS_JS_URL = "https://cdnjs.cloudflare.com/ajax/libs/hls.js/1.5.15/hls.min.js";

function ensure_hlsjs(callback) {
	if (window.Hls) {
		callback();
		return;
	}
	frappe.require(HLS_JS_URL, callback);
}

frappe.pages["tracking_live_video"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Live Camera"),
		single_column: true,
	});

	new LiveVideoPage(page);
};

class LiveVideoPage {
	constructor(page) {
		this.page = page;
		this.hls = null;
		this.$body = $(`<div class="tracking_live_video"></div>`).appendTo(page.body);
		this._render_shell();
		this._load_devices();
	}

	_render_shell() {
		this.$body.html(`
			<div class="d-flex flex-wrap align-items-end mb-3" style="gap: 8px;">
				<div>
					<label class="text-muted small d-block">${__("Device")}</label>
					<select class="form-control erp-tracking-device-select" style="min-width: 220px;"></select>
				</div>
				<div>
					<label class="text-muted small d-block">${__("Channel")}</label>
					<input type="number" class="form-control erp-tracking-channel" value="0" min="0" style="width: 100px;">
				</div>
				<button class="btn btn-primary erp-tracking-play">${__("Play")}</button>
			</div>
			<div class="erp-tracking-video-wrapper" style="background:#000; border-radius:6px; max-width: 720px;">
				<video class="erp-tracking-video" controls style="width:100%; display:block; border-radius:6px;"></video>
			</div>
			<div class="text-muted small mt-2 erp-tracking-video-status"></div>
		`);

		this.$deviceSelect = this.$body.find(".erp-tracking-device-select");
		this.$channel = this.$body.find(".erp-tracking-channel");
		this.$video = this.$body.find(".erp-tracking-video");
		this.$status = this.$body.find(".erp-tracking-video-status");

		this.$body.find(".erp-tracking-play").on("click", () => this.play());
	}

	_load_devices() {
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
	}

	play() {
		const device_id = this.$deviceSelect.val();
		const channel = this.$channel.val() || 0;

		if (!device_id) {
			frappe.msgprint(__("Please select a device."));
			return;
		}

		const src = `/api/method/erp_tracking.api.get_stream_playlist?device_id=${device_id}&channel=${channel}`;
		this.$status.text(__("Connecting..."));

		ensure_hlsjs(() => {
			if (this.hls) {
				this.hls.destroy();
				this.hls = null;
			}

			if (window.Hls.isSupported()) {
				this.hls = new Hls();
				this.hls.on(Hls.Events.ERROR, (event, data) => {
					if (data.fatal) {
						this.$status.text(`🔴 ${__("Stream error: {0}", [data.details || __("unknown")])}`);
					}
				});
				this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
					this.$status.text(`🟢 ${__("Live")}`);
					this.$video[0].play().catch(() => {});
				});
				this.hls.loadSource(src);
				this.hls.attachMedia(this.$video[0]);
			} else if (this.$video[0].canPlayType("application/vnd.apple.mpegurl")) {
				// Safari has native HLS support and doesn't need hls.js.
				this.$video[0].src = src;
				this.$video[0].play().catch(() => {});
				this.$status.text(`🟢 ${__("Live")}`);
			} else {
				this.$status.text(`🔴 ${__("HLS playback is not supported in this browser.")}`);
			}
		});
	}
}
