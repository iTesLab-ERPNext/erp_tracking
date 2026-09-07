// Devices list. Clicking a row opens the device detail page.
frappe.pages["tracking-devices"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Devices"),
		single_column: true,
	});

	await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "devices",
		filters: [
			{
				fieldname: "status",
				label: __("Status"),
				fieldtype: "Select",
				options: [
					{ value: "", label: __("All statuses") },
					{ value: "online", label: __("Online") },
					{ value: "offline", label: __("Offline") },
					{ value: "unknown", label: __("Unknown") },
				],
			},
		],
		column_overrides: {
			name: (value, row) =>
				`<a class="erpt-link" data-device="${row.id}">${frappe.utils.escape_html(value || "")}</a>`,
		},
		on_row_click: (row) => frappe.set_route("tracking-device-detail", row.id),
	});

	// `status` is not a documented /devices parameter, so it is applied here.
	const original_render = engine.render.bind(engine);
	engine.render = function (data) {
		const status = engine.fields.status ? engine.fields.status.get_value() : "";
		if (status) data.items = (data.items || []).filter((row) => row.status === status);
		original_render(data);
	};

	await engine.setup();
	page.add_menu_item(__("Live Positions"), () => frappe.set_route("tracking-positions"));
	wrapper.erp_tracking_engine = engine;
};
