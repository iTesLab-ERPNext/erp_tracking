// Orders - generic list page backed by erp_tracking.ListEngine.
frappe.pages["tracking-orders"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Orders"),
		single_column: true,
	});

	await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "orders",
		filters: [],
		column_overrides: {},
	});

	await engine.setup();
	wrapper.erp_tracking_engine = engine;
};
