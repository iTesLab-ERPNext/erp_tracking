// Server health - polls the unauthenticated /health probe.
frappe.pages["tracking-health"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Server Health"),
		single_column: true,
	});

	const $container = $(`<div class="erpt-page"><div class="erpt-body"></div></div>`).appendTo(page.main);
	const $body = $container.find(".erpt-body");
	if (await erp_tracking.guard($body)) return;

	page.set_primary_action(__("Check Now"), () => check());
	await check();

	let timer = setInterval(check, 60000);
	$(wrapper).on("remove", () => clearInterval(timer));

	async function check() {
		const response = await erp_tracking.call("erp_tracking.api.get_server_health", {}, { silent: true });
		const data = (response.success && response.data) || { healthy: false };

		$body.html(`
			<div class="erpt-card ${data.healthy ? "success" : "danger"}" style="margin-top:15px">
				<div class="erpt-card-value">
					<span class="indicator-pill ${data.healthy ? "green" : "red"}">
						${data.healthy ? __("Healthy") : __("Unavailable")}
					</span>
				</div>
				<div class="erpt-card-label">${
					data.healthy
						? __("HTTP {0} · {1} ms", [data.status_code, data.response_time_ms])
						: frappe.utils.escape_html(response.message || __("The Traccar server did not respond."))
				}</div>
			</div>
			<div class="erpt-detail-grid">
				<div><div class="erpt-detail-label">${__("Status")}</div><div class="erpt-detail-value">${
					frappe.utils.escape_html(data.status || (data.healthy ? "OK" : "—"))
				}</div></div>
				<div><div class="erpt-detail-label">${__("Response time")}</div><div class="erpt-detail-value">${
					data.response_time_ms !== undefined ? data.response_time_ms + " ms" : "—"
				}</div></div>
				<div><div class="erpt-detail-label">${__("Last check")}</div><div class="erpt-detail-value">${
					erp_tracking.format.datetime(data.checked_at) || "—"
				}</div></div>
			</div>`);
	}
};
