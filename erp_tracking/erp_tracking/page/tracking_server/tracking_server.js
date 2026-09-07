// Server information - only the fields the /server schema actually returns.
frappe.pages["tracking-server"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Server Information"),
		single_column: true,
	});

	const $container = $(`<div class="erpt-page"><div class="erpt-body"></div></div>`).appendTo(page.main);
	const $body = $container.find(".erpt-body");
	if (await erp_tracking.guard($body)) return;

	page.set_secondary_action(__("Refresh"), () => load(true));
	await load();

	async function load(refresh = false) {
		$body.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);
		const response = await erp_tracking.call("erp_tracking.api.get_server_info", { refresh: refresh ? 1 : 0 });
		if (!response.success) {
			$body.html(erp_tracking.empty_state({ title: response.message }));
			return;
		}

		const info = response.data || {};
		const rows = [
			[__("Version"), info.version],
			[__("Map"), info.map],
			[__("Map URL"), info.mapUrl],
			[__("POI Layer"), info.poiLayer],
			[__("Latitude"), info.latitude],
			[__("Longitude"), info.longitude],
			[__("Zoom"), info.zoom],
			[__("Coordinate Format"), info.coordinateFormat],
			[__("Registration Open"), erp_tracking.format.check(info.registration)],
			[__("Read Only"), erp_tracking.format.check(info.readonly)],
			[__("Device Read Only"), erp_tracking.format.check(info.deviceReadonly)],
			[__("Limit Commands"), erp_tracking.format.check(info.limitCommands)],
			[__("Force Settings"), erp_tracking.format.check(info.forceSettings)],
			[__("OpenID Enabled"), erp_tracking.format.check(info.openIdEnabled)],
			[__("OpenID Required"), erp_tracking.format.check(info.openIdForce)],
			[__("Announcement"), info.announcement],
		];

		$body.html(`
			<div class="erpt-detail-grid" style="margin-top:15px">
				${rows
					.map(
						([label, value]) => `
					<div>
						<div class="erpt-detail-label">${label}</div>
						<div class="erpt-detail-value">${
							value === undefined || value === null || value === ""
								? "&mdash;"
								: frappe.utils.escape_html(String(value))
						}</div>
					</div>`
					)
					.join("")}
			</div>`);
	}
};
