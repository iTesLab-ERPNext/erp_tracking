// Live camera. The HLS playlist and its segments are relayed by the server so
// that no Traccar credential is ever handed to the browser.
frappe.pages["tracking-camera"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Live Camera"),
		single_column: true,
	});

	const $container = $(`<div class="erpt-page"><div class="erpt-body"></div></div>`).appendTo(page.main);
	const $body = $container.find(".erpt-body");

	const config = await erp_tracking.get_config();
	if (await erp_tracking.guard($body)) return;

	if (!config.live_video) {
		$body.html(
			erp_tracking.empty_state({
				title: __("Live video is turned off"),
				message: __("Enable live video in Traccar Settings to stream device cameras."),
			})
		);
		return;
	}

	const device_field = page.add_field({ fieldname: "device", label: __("Device"), fieldtype: "Autocomplete", reqd: 1 });
	const channel_field = page.add_field({ fieldname: "channel", label: __("Channel"), fieldtype: "Int", default: 0 });

	const options = await erp_tracking.filter_options(["devices"]);
	device_field.set_data((options.devices || []).map((d) => ({ label: d.label, value: String(d.value) })));

	page.set_primary_action(__("Start Stream"), () => start());
	$body.html(erp_tracking.empty_state({ title: __("Choose a device and a channel") }));

	async function start() {
		const device_id = device_field.get_value();
		if (!device_id) {
			frappe.show_alert({ message: __("Select a device"), indicator: "orange" });
			return;
		}

		const response = await erp_tracking.call("erp_tracking.api.get_stream_playlist_url", {
			device_id,
			channel: channel_field.get_value() || 0,
		});
		if (!response.success) return;

		$body.html('<video class="erpt-video" controls autoplay muted playsinline></video>');
		const video = $body.find("video").get(0);
		const url = response.data.playlist_url;

		if (video.canPlayType("application/vnd.apple.mpegurl")) {
			video.src = url;
			return;
		}

		if (!window.Hls) {
			await load_hls_js();
		}
		if (window.Hls && window.Hls.isSupported()) {
			const hls = new window.Hls();
			hls.loadSource(url);
			hls.attachMedia(video);
		} else {
			$body.html(
				erp_tracking.empty_state({
					title: __("This browser cannot play HLS"),
					message: __("Open the stream in Safari, or install an HLS-capable browser."),
				})
			);
		}
	}

	function load_hls_js() {
		return new Promise((resolve) => {
			const script = document.createElement("script");
			script.src = "https://cdn.jsdelivr.net/npm/hls.js@1.5.13/dist/hls.min.js";
			script.onload = resolve;
			script.onerror = resolve;
			document.head.appendChild(script);
		});
	}
};
