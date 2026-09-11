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

	// "Overview" is a fleet-wide KPI/chart dashboard built from the existing
	// trips/summary/events reports, not a single Traccar report of its own,
	// so it is handled before the REPORT_CONFIG-driven lookup below.
	if (report === "overview") {
		page.set_title(__("Fleet Overview"));
		add_report_switcher(page, report, (await erp_tracking.call("erp_tracking.api.get_report_meta")).data);
		const overview = new FleetOverview(page, page.main);
		await overview.setup();
		wrapper.erp_tracking_engine = overview;
		return;
	}

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
	if (current !== "overview") {
		page.add_menu_item(__("Go to Fleet Overview"), () => frappe.set_route("tracking-reports", "overview"));
	}
	Object.keys(all_meta || {}).forEach((name) => {
		if (name === current) return;
		page.add_menu_item(__("Go to {0}", [__(all_meta[name].label)]), () =>
			frappe.set_route("tracking-reports", name)
		);
	});
}

/**
 * Fleet Overview - KPI cards, charts and device/driver/group breakdowns.
 * Everything here comes from erp_tracking.api.get_fleet_overview, which is
 * itself built purely from the existing trips/summary/events reports (see
 * reports.build_fleet_overview) - no new Traccar endpoint is introduced.
 */
class FleetOverview {
	constructor(page, parent) {
		this.page = page;
		this.$container = $(`
			<div class="erpt-page">
				<div class="erpt-kpi"></div>
				<div class="erpt-charts" style="display:flex;flex-wrap:wrap;gap:20px;margin:15px 0"></div>
			</div>`).appendTo(parent);
		this.$kpi = this.$container.find(".erpt-kpi");
		this.$charts = this.$container.find(".erpt-charts");
	}

	async setup() {
		if (await erp_tracking.guard(this.$kpi)) return;
		this.build_filters();
		this.page.set_primary_action(__("Generate"), () => this.run());
		this.page.set_secondary_action(__("Refresh"), () => this.run());
		await this.load_options();
		this.run();
	}

	build_filters() {
		this.fields = {};
		this.fields.deviceId = this.page.add_field({
			fieldname: "deviceId",
			label: __("Device"),
			fieldtype: "MultiSelectList",
			get_data: () => this.device_options(),
		});
		this.fields.groupId = this.page.add_field({
			fieldname: "groupId",
			label: __("Group"),
			fieldtype: "MultiSelectList",
			get_data: () => this.group_options(),
		});
		this.fields.from = this.page.add_field({
			fieldname: "from",
			label: __("From"),
			fieldtype: "Date",
			default: erp_tracking.default_from(),
		});
		this.fields.to = this.page.add_field({
			fieldname: "to",
			label: __("To"),
			fieldtype: "Date",
			default: erp_tracking.default_to(),
		});
		this.fields.from.set_input(erp_tracking.default_from());
		this.fields.to.set_input(erp_tracking.default_to());
	}

	async load_options() {
		this.options_data = await erp_tracking.filter_options(["devices", "groups"]);
	}

	device_options() {
		return ((this.options_data && this.options_data.devices) || []).map((d) => ({
			value: String(d.value),
			description: d.label,
		}));
	}

	group_options() {
		return ((this.options_data && this.options_data.groups) || []).map((g) => ({
			value: String(g.value),
			description: g.label,
		}));
	}

	current_filters() {
		const filters = {};
		Object.keys(this.fields).forEach((fieldname) => {
			const value = this.fields[fieldname].get_value();
			if (value === undefined || value === null || value === "" || (Array.isArray(value) && !value.length)) return;
			filters[fieldname] = value;
		});
		return filters;
	}

	async run() {
		this.$kpi.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);
		this.$charts.empty();

		const filters = this.current_filters();
		const response = await erp_tracking.call("erp_tracking.api.get_fleet_overview", {
			from_time: filters.from || erp_tracking.default_from(),
			to_time: filters.to || erp_tracking.default_to(),
			device_ids: JSON.stringify((filters.deviceId || []).map(Number)),
			group_ids: JSON.stringify((filters.groupId || []).map(Number)),
		});

		if (!response.success) {
			this.$kpi.html(erp_tracking.empty_state({ title: response.message || __("Could not build the overview") }));
			return;
		}
		this.render(response.data);
	}

	render(data) {
		erp_tracking.render_cards(this.$kpi, data.kpi || []);

		if (data.empty) {
			this.$charts.html(
				erp_tracking.empty_state({
					title: __("No devices or groups selected"),
					message: __("Pick at least one device or group above, or leave both blank to include the whole fleet."),
				})
			);
			return;
		}

		this.render_series_chart(__("Trips per Day"), data.trips_per_day.labels, [
			{ name: __("Trips"), values: data.trips_per_day.values },
		]);
		this.render_breakdown_chart(__("Distance by Device (km)"), data.by_device, "#2490ef");
		this.render_breakdown_chart(__("Distance by Driver (km)"), data.by_driver, "#28a745");
		this.render_breakdown_chart(__("Distance by Group (km)"), data.by_group, "#f5a623");
	}

	render_series_chart(title, labels, datasets) {
		const $card = $(
			`<div class="erpt-chart-card" style="flex:1 1 420px;min-width:320px"><h6>${frappe.utils.escape_html(
				title
			)}</h6><div></div></div>`
		).appendTo(this.$charts);
		if (!labels.length) {
			$card.find("div").html(erp_tracking.empty_state({ title: __("No data for this period") }));
			return;
		}
		new frappe.Chart($card.find("div").get(0), {
			data: { labels, datasets },
			type: "bar",
			height: 220,
			colors: ["#2490ef"],
		});
	}

	render_breakdown_chart(title, rows, color) {
		const $card = $(
			`<div class="erpt-chart-card" style="flex:1 1 420px;min-width:320px"><h6>${frappe.utils.escape_html(
				title
			)}</h6><div></div></div>`
		).appendTo(this.$charts);
		if (!rows.length) {
			$card.find("div").html(erp_tracking.empty_state({ title: __("No data for this period") }));
			return;
		}
		new frappe.Chart($card.find("div").get(0), {
			data: { labels: rows.map((r) => r.label), datasets: [{ name: title, values: rows.map((r) => r.distance) }] },
			type: "bar",
			height: 220,
			colors: [color],
		});
	}
}
