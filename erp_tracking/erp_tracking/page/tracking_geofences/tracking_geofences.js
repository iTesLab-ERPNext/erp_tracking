// Geofences. Traccar defines POST/PUT/DELETE on /geofences, so managers get
// create, edit and delete; everyone else gets a read-only list.
frappe.pages["tracking-geofences"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Geofences"),
		single_column: true,
	});

	const config = await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "geofences",
		filters: [
			{ fieldname: "deviceId", label: __("Device"), fieldtype: "Autocomplete", source: "devices" },
			{ fieldname: "groupId", label: __("Group"), fieldtype: "Autocomplete", source: "groups" },
		],
		primary_action: config.can_manage
			? { label: __("New Geofence"), action: () => open_geofence_dialog(engine) }
			: null,
		on_row_click: (row) => (config.can_manage ? open_geofence_dialog(engine, row) : null),
	});

	await engine.setup();
	wrapper.erp_tracking_engine = engine;
};

function open_geofence_dialog(engine, geofence) {
	const editing = Boolean(geofence && geofence.id);
	const dialog = new frappe.ui.Dialog({
		title: editing ? __("Edit Geofence") : __("New Geofence"),
		fields: [
			{ fieldname: "name", label: __("Name"), fieldtype: "Data", reqd: 1, default: geofence?.name },
			{
				fieldname: "description",
				label: __("Description"),
				fieldtype: "Data",
				default: geofence?.description,
			},
			{
				fieldname: "area",
				label: __("Area (WKT)"),
				fieldtype: "Small Text",
				reqd: 1,
				default: geofence?.area,
				description: __("For example: CIRCLE (36.80 10.18, 500)"),
			},
			{
				fieldname: "calendarId",
				label: __("Calendar ID"),
				fieldtype: "Int",
				default: geofence?.calendarId,
			},
		],
		primary_action_label: __("Save"),
		async primary_action(values) {
			const response = await erp_tracking.call("erp_tracking.api.save_geofence", {
				payload: JSON.stringify(values),
				geofence_id: editing ? geofence.id : null,
			});
			if (response.success) {
				dialog.hide();
				frappe.show_alert({ message: __("Geofence saved"), indicator: "green" });
				engine.refresh(true);
			}
		},
	});

	if (editing) {
		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete this geofence?"), async () => {
				const response = await erp_tracking.call("erp_tracking.api.delete_geofence", {
					geofence_id: geofence.id,
				});
				if (response.success) {
					dialog.hide();
					frappe.show_alert({ message: __("Geofence deleted"), indicator: "green" });
					engine.refresh(true);
				}
			});
		});
	}

	dialog.show();
}
