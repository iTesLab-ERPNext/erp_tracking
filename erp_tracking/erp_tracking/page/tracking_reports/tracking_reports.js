// One page for every report. The report name comes from the route:
//   tracking-reports/trips, tracking-reports/summary, tracking-reports/route ...
frappe.pages["tracking-reports"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Tracking Reports"),
		single_column: true,
	});
	wrapper.erp_tracking_page = page;
};

frappe.pages["tracking-reports"].on_page_show = async function (wrapper) {
	const report = frappe.get_route()[1] || "summary";
	if (wrapper.erp_tracking_report === report) return;
	wrapper.erp_tracking_report = report;

	const page = wrapper.erp_tracking_page;
	page.clear_fields();
	page.clear_menu();
	page.clear_primary_action();
	page.clear_secondary_action();
	$(page.main).empty();

	await erp_tracking.get_config();

	const meta_response = await erp_tracking.call("erp_tracking.api.get_report_meta");
	const meta = (meta_response.data || {})[report];

	if (!meta) {
		$(page.main).html(
			erp_tracking.empty_state({
				title: __("Unknown report"),
				message: __("Choose one of: summary, trips, stops, events, route, geofences."),
			})
		);
		return;
	}

	page.set_title(__(meta.label));
	add_report_switcher(page, report, meta_response.data);

	const $mount = $('<div></div>').appendTo(page.main);
	const engine = new erp_tracking.ReportEngine({
		page,
		parent: $mount,
		report,
		meta,
		options: {
			column_overrides: {
				maxSpeed: (value) => erp_tracking.format.speed(value),
				averageSpeed: (value) => erp_tracking.format.speed(value),
				speed: (value) => erp_tracking.format.speed(value),
				distance: (value) => erp_tracking.format.distance(value),
			},
		},
		on_render: (data) => {
			if (report !== "route") return;
			let $map = $(page.main).find(".erpt-route-map");
			if (!$map.length) {
				$map = $('<div class="erpt-route-map" style="height:380px;margin-bottom:15px"></div>').prependTo($mount);
			}
			erp_tracking.map.render($map.get(0), { points: (data.items || []).slice(0, 200), track: data.track });
		},
	});

	await engine.setup();
	wrapper.erp_tracking_engine = engine;
};

function add_report_switcher(page, current, all_meta) {
	Object.keys(all_meta || {}).forEach((name) => {
		if (name === current) return;
		page.add_menu_item(__("Go to {0}", [__(all_meta[name].label)]), () =>
			frappe.set_route("tracking-reports", name)
		);
	});
}
