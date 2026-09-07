// Calendars - generic list page backed by erp_tracking.ListEngine.
frappe.pages["tracking-calendars"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Calendars"),
		single_column: true,
	});

	await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "calendars",
		filters: [],
		column_overrides: {},
	});

	await engine.setup();
	wrapper.erp_tracking_engine = engine;
};
