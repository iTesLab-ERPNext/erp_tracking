// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

const HEALTH_AUTO_REFRESH_MS = 30000;

frappe.pages["tracking_health"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Server Health"),
		single_column: true,
	});

	const $body = $(`
		<div class="tracking_health text-center p-5">
			<div class="tracking_health-icon" style="font-size: 4em;">⚪</div>
			<div class="tracking_health-status h3 mt-2"></div>
			<div class="text-muted tracking_health-detail mt-3"></div>
		</div>
	`).appendTo(page.body);

	page.set_primary_action(__("Check Now"), () => check(), "fa fa-refresh");

	function check() {
		frappe.call({
			method: "erp_tracking.api.get_health",
			callback: (r) => {
				const result = r.message || {};
				render(result);
			},
			error: () => {
				render({ success: false, healthy: false, message: __("Unable to reach the server."), response_time_ms: null });
			},
		});
	}

	function render(result) {
		const is_config = result.error === "TraccarConfigurationError";
		const now = frappe.datetime.now_datetime();

		if (is_config) {
			$body.find(".tracking_health-icon").text("⚪");
			$body.find(".tracking_health-status").html(__("Not Configured"));
		} else if (result.healthy) {
			$body.find(".tracking_health-icon").text("🟢");
			$body.find(".tracking_health-status").html(`<span class="text-success">${__("HEALTHY")}</span>`);
		} else {
			$body.find(".tracking_health-icon").text("🔴");
			$body.find(".tracking_health-status").html(`<span class="text-danger">${__("UNAVAILABLE")}</span>`);
		}

		const detail_lines = [];
		if (result.response_time_ms != null) {
			detail_lines.push(__("Response time: {0} ms", [result.response_time_ms]));
		}
		detail_lines.push(__("Last check: {0}", [frappe.datetime.str_to_user(now)]));
		if (!result.success && !is_config && result.message) {
			detail_lines.push(frappe.utils.escape_html(result.message));
		}

		$body.find(".tracking_health-detail").html(detail_lines.join("<br>"));
	}

	check();
	const interval = setInterval(check, HEALTH_AUTO_REFRESH_MS);
	$(wrapper).on("hide", () => clearInterval(interval));
};
