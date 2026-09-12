// Reports hub - a single page with a report-type dropdown, mirroring the
// reports available in the reference React project (see ReportsMenu there):
// Combined, Events, Geofence Visits, Trips, Stops, Route/Positions, Summary,
// Chart, Statistics, Audit. Six of these (trips/stops/summary/events/route/
// geofences) are just the existing erp_tracking.ReportEngine mounted here
// instead of on the tracking-reports page; Positions and Chart are small,
// self-contained views built the same way tracking-position-history already
// is; Statistics and Audit already have complete, dedicated pages, so this
// page links to those rather than duplicating them.
frappe.pages["erp-tracking-reports"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Reports"),
		single_column: true,
	});
	wrapper.erp_tracking_view = new ReportsHub(page);
	await wrapper.erp_tracking_view.setup();
};

class ReportsHub {
	constructor(page) {
		this.page = page;
		this.$container = $(`
			<div class="erpt-page">
				<div class="erpt-report-switcher" style="max-width:320px;margin-bottom:15px">
					<label class="text-muted small">${__("Report Type")}</label>
					<select class="form-control erpt-report-select"></select>
				</div>
				<div class="erpt-report-mount"></div>
			</div>`).appendTo(page.main);

		this.$select = this.$container.find(".erpt-report-select");
		this.$mount = this.$container.find(".erpt-report-mount");
	}

	async setup() {
		if (await erp_tracking.guard(this.$mount)) return;
		this.config = await erp_tracking.get_config();

		const meta_response = await erp_tracking.call("erp_tracking.api.get_report_meta");
		this.report_meta = meta_response.success ? meta_response.data : {};

		// Same order as the reference project's Reports menu.
		const options = [
			{ value: "combined", label: __("Combined") },
			{ value: "events", label: __("Events") },
			{ value: "geofences", label: __("Geofence Visits") },
			{ value: "trips", label: __("Trips") },
			{ value: "stops", label: __("Stops") },
			{ value: "positions", label: __("Route (Positions)") },
			{ value: "summary", label: __("Summary") },
			{ value: "chart", label: __("Chart") },
		];
		if (this.config.can_manage) {
			options.push({ value: "statistics", label: __("Statistics") });
			options.push({ value: "audit", label: __("Audit") });
		}

		options.forEach((opt) => this.$select.append(`<option value="${opt.value}">${opt.label}</option>`));
		this.$select.val("summary");
		this.$select.on("change", () => this.render_view(this.$select.val()));

		this.render_view(this.$select.val() || "summary");
	}

	reset_page_chrome() {
		this.page.clear_fields();
		this.page.clear_menu();
		this.page.clear_primary_action();
		this.page.clear_secondary_action();
		this.$mount.empty();
	}

	render_view(key) {
		this.reset_page_chrome();
		const $view = $("<div></div>").appendTo(this.$mount);

		const report_engine_meta = this.report_meta[key];
		if (report_engine_meta) {
			this.render_report_engine(key, report_engine_meta, $view);
			return;
		}

		const builders = {
			positions: () => this.render_positions($view),
			combined: () => this.render_combined($view),
			chart: () => this.render_chart($view),
			statistics: () => this.render_redirect($view, __("Statistics"), "tracking-statistics"),
			audit: () => this.render_redirect($view, __("Audit"), "tracking-audit"),
		};
		(builders[key] || builders.positions)();
	}

	// -------------------------------------------------------------------
	// Trips / Stops / Summary / Events / Route / Geofence Visits - these
	// are exactly the reports already served by erp_tracking.ReportEngine
	// on the tracking-reports page; mounting the same engine here means
	// the logic, filters, columns and export options are identical.
	// -------------------------------------------------------------------
	render_report_engine(report, meta, $view) {
		const engine = new erp_tracking.ReportEngine({
			page: this.page,
			parent: $view,
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
				let $map = $view.find(".erpt-route-map");
				if (!$map.length) {
					$map = $('<div class="erpt-route-map" style="height:380px;margin-bottom:15px"></div>').prependTo($view);
				}
				erp_tracking.map.render($map.get(0), { points: (data.items || []).slice(0, 200), track: data.track });
			},
		});
		engine.setup();
	}

	// -------------------------------------------------------------------
	// Route / Positions - the reference project's "Route" report is a raw
	// position list for one device (GET /api/positions), which in this app
	// is erp_tracking.api.get_position_history - the exact same call the
	// dedicated Position History page already makes.
	// -------------------------------------------------------------------
	async render_positions($view) {
		$view.html(`
			<div class="erpt-map-wrapper" style="height:380px;margin-bottom:15px"></div>
			<div class="erpt-body"></div>
			<div class="erpt-footer"></div>`);
		const $map = $view.find(".erpt-map-wrapper");
		const $body = $view.find(".erpt-body");
		const $footer = $view.find(".erpt-footer");

		const device_field = this.page.add_field({
			fieldname: "device",
			label: __("Device"),
			fieldtype: "Autocomplete",
			reqd: 1,
		});
		const from_field = this.page.add_field({ fieldname: "from", label: __("From Date"), fieldtype: "Date" });
		const to_field = this.page.add_field({ fieldname: "to", label: __("To Date"), fieldtype: "Date" });
		from_field.set_input(erp_tracking.default_from());
		to_field.set_input(erp_tracking.default_to());

		const options = await erp_tracking.filter_options(["devices"]);
		device_field.set_data((options.devices || []).map((d) => ({ label: d.label, value: String(d.value) })));

		let offset = 0;
		const page_length = this.config.page_length || 20;

		const load = async () => {
			const device_id = device_field.get_value();
			if (!device_id) {
				frappe.show_alert({ message: __("Select a device"), indicator: "orange" });
				return;
			}
			$body.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);
			const response = await erp_tracking.call("erp_tracking.api.get_position_history", {
				device_id,
				from_time: from_field.get_value(),
				to_time: to_field.get_value(),
				limit: page_length,
				offset,
			});
			if (!response.success) {
				$body.html(erp_tracking.empty_state({ title: response.message }));
				$footer.empty();
				return;
			}

			const data = response.data;
			const rows = data.items || [];
			erp_tracking.map.render($map.get(0), { points: rows.slice(0, 200), track: data.track });

			if (!rows.length) {
				$body.html(erp_tracking.empty_state({ title: __("No positions in this period") }));
				$footer.empty();
				return;
			}

			$body.empty();
			const $table = $('<div class="erpt-datatable"></div>').appendTo($body);
			new frappe.DataTable($table.get(0), {
				columns: erp_tracking.to_datatable_columns(
					[
						{ fieldname: "fixTime", label: "Time", fieldtype: "Datetime", width: 165 },
						{ fieldname: "latitude", label: "Latitude", fieldtype: "Float", width: 110 },
						{ fieldname: "longitude", label: "Longitude", fieldtype: "Float", width: 110 },
						{ fieldname: "speed", label: "Speed", fieldtype: "Data", width: 100 },
						{ fieldname: "course", label: "Course", fieldtype: "Float", width: 90 },
						{ fieldname: "altitude", label: "Altitude (m)", fieldtype: "Float", width: 110 },
						{ fieldname: "accuracy", label: "Accuracy (m)", fieldtype: "Float", width: 110 },
						{ fieldname: "address", label: "Address", fieldtype: "Data", width: 280 },
					],
					{ speed: (value) => erp_tracking.format.speed(value) }
				),
				data: rows,
				layout: "fluid",
			});

			erp_tracking.pagination(
				$footer,
				{
					offset: data.offset,
					page_length: data.limit || page_length,
					count: rows.length,
					total: data.total,
					has_more: data.offset + rows.length < data.total,
				},
				(new_offset) => {
					offset = new_offset;
					load();
				}
			);
		};

		this.page.set_primary_action(__("Show"), () => {
			offset = 0;
			load();
		});
		erp_tracking.add_export_menu(
			this.page,
			(fmt) => {
				const device_id = device_field.get_value();
				if (!device_id) {
					frappe.show_alert({ message: __("Select a device"), indicator: "orange" });
					return;
				}
				erp_tracking.download("erp_tracking.api.export_positions", {
					device_id,
					from_time: from_field.get_value(),
					to_time: to_field.get_value(),
					fmt,
				});
			},
			["csv", "xlsx", "pdf", "gpx", "kml"]
		);

		$body.html(
			erp_tracking.empty_state({
				title: __("Choose a device and a period"),
				message: __("Traccar returns the full track for the selected window."),
			})
		);
	}

	// -------------------------------------------------------------------
	// Combined - GET /reports/combined (route + events + positions per
	// device). The reference project overlays this on a map; here it is
	// shown as a flat table of the events it returns for each selected
	// device, which is the same "combined" data in its simplest form.
	// -------------------------------------------------------------------
	async render_combined($view) {
		$view.html('<div class="erpt-body"></div>');
		const $body = $view.find(".erpt-body");

		const device_field = this.page.add_field({
			fieldname: "deviceId",
			label: __("Devices"),
			fieldtype: "MultiSelectList",
			get_data: () => this.device_choices(),
		});
		const group_field = this.page.add_field({
			fieldname: "groupId",
			label: __("Groups"),
			fieldtype: "MultiSelectList",
			get_data: () => this.group_choices(),
		});
		const from_field = this.page.add_field({ fieldname: "from", label: __("From Date"), fieldtype: "Date" });
		const to_field = this.page.add_field({ fieldname: "to", label: __("To Date"), fieldtype: "Date" });
		from_field.set_input(erp_tracking.default_from());
		to_field.set_input(erp_tracking.default_to());

		await this.load_filter_options();

		this.page.set_primary_action(__("Generate"), async () => {
			const device_ids = (device_field.get_value() || []).map(Number);
			const group_ids = (group_field.get_value() || []).map(Number);
			if (!device_ids.length && !group_ids.length) {
				frappe.show_alert({ message: __("Select at least one device or group"), indicator: "orange" });
				return;
			}

			$body.html(`<div class="erpt-loading text-muted">${__("Generating...")}</div>`);
			const response = await erp_tracking.call("erp_tracking.api.get_combined_report", {
				filters: JSON.stringify({
					deviceId: device_ids,
					groupId: group_ids,
					from: from_field.get_value(),
					to: to_field.get_value(),
				}),
			});

			if (!response.success) {
				$body.html(erp_tracking.empty_state({ title: response.message || __("Could not generate the report") }));
				return;
			}

			const rows = [];
			(response.data.items || []).forEach((item) => {
				(item.events || []).forEach((event) => {
					rows.push({
						deviceName: item.deviceName,
						eventTime: event.eventTime,
						type: event.type,
						attributes:
							event.attributes && Object.keys(event.attributes).length ? JSON.stringify(event.attributes) : "",
					});
				});
			});

			if (!rows.length) {
				$body.html(erp_tracking.empty_state({ title: __("No events in this period") }));
				return;
			}

			$body.empty();
			const $table = $('<div class="erpt-datatable"></div>').appendTo($body);
			new frappe.DataTable($table.get(0), {
				columns: erp_tracking.to_datatable_columns([
					{ fieldname: "deviceName", label: "Device", fieldtype: "Data", width: 160 },
					{ fieldname: "eventTime", label: "Time", fieldtype: "Datetime", width: 165 },
					{ fieldname: "type", label: "Event Type", fieldtype: "Data", width: 160 },
					{ fieldname: "attributes", label: "Attributes", fieldtype: "Data", width: 260 },
				]),
				data: rows,
				layout: "fluid",
			});
		});

		$body.html(
			erp_tracking.empty_state({
				title: __("Choose at least one device or group and a period"),
			})
		);
	}

	// -------------------------------------------------------------------
	// Chart - a single numeric field from GET /reports/route, plotted over
	// time for one device (frappe.Chart, already used on the Statistics
	// page, keeps this consistent with the rest of the app).
	// -------------------------------------------------------------------
	async render_chart($view) {
		$view.html('<div class="erpt-chart-wrapper" style="min-height:260px"></div>');
		const $chart = $view.find(".erpt-chart-wrapper");

		const device_field = this.page.add_field({
			fieldname: "device",
			label: __("Device"),
			fieldtype: "Autocomplete",
			reqd: 1,
		});
		const from_field = this.page.add_field({ fieldname: "from", label: __("From Date"), fieldtype: "Date" });
		const to_field = this.page.add_field({ fieldname: "to", label: __("To Date"), fieldtype: "Date" });
		const field_field = this.page.add_field({
			fieldname: "field",
			label: __("Field"),
			fieldtype: "Select",
			options: [
				{ value: "speed", label: __("Speed") },
				{ value: "altitude", label: __("Altitude") },
				{ value: "course", label: __("Course") },
				{ value: "accuracy", label: __("Accuracy") },
			],
		});
		from_field.set_input(erp_tracking.default_from());
		to_field.set_input(erp_tracking.default_to());
		field_field.set_value("speed");

		const options = await erp_tracking.filter_options(["devices"]);
		device_field.set_data((options.devices || []).map((d) => ({ label: d.label, value: String(d.value) })));

		this.page.set_primary_action(__("Generate"), async () => {
			const device_id = device_field.get_value();
			if (!device_id) {
				frappe.show_alert({ message: __("Select a device"), indicator: "orange" });
				return;
			}

			$chart.html(`<div class="erpt-loading text-muted">${__("Generating...")}</div>`);
			const response = await erp_tracking.call("erp_tracking.api.run_report", {
				report: "route",
				filters: JSON.stringify({
					deviceId: [Number(device_id)],
					from: from_field.get_value(),
					to: to_field.get_value(),
				}),
			});

			if (!response.success) {
				$chart.html(erp_tracking.empty_state({ title: response.message || __("Could not generate the chart") }));
				return;
			}

			const rows = response.data.items || [];
			if (!rows.length) {
				$chart.html(erp_tracking.empty_state({ title: __("No positions in this period") }));
				return;
			}

			const field = field_field.get_value() || "speed";
			$chart.empty();
			new frappe.Chart($chart.get(0), {
				data: {
					labels: rows.map((r) => frappe.datetime.str_to_user(r.fixTime)),
					datasets: [{ name: __(field), values: rows.map((r) => r[field] || 0) }],
				},
				type: "line",
				height: 260,
				colors: ["#2490ef"],
			});
		});

		$chart.html(erp_tracking.empty_state({ title: __("Choose a device, a period and a field") }));
	}

	render_redirect($view, label, route) {
		$view.html(
			erp_tracking.empty_state({
				title: __("{0} has its own page", [label]),
				message: __("Manager-only server diagnostics live there so they are not duplicated here."),
			})
		);
		$('<button class="btn btn-default btn-sm">' + __("Open {0}", [label]) + "</button>")
			.appendTo($view)
			.on("click", () => frappe.set_route(route));
	}

	async load_filter_options() {
		if (this.options_data) return this.options_data;
		this.options_data = await erp_tracking.filter_options(["devices", "groups"]);
		return this.options_data;
	}

	device_choices() {
		return ((this.options_data && this.options_data.devices) || []).map((d) => ({
			value: String(d.value),
			description: d.label,
		}));
	}

	group_choices() {
		return ((this.options_data && this.options_data.groups) || []).map((g) => ({
			value: String(g.value),
			description: g.label,
		}));
	}
}
