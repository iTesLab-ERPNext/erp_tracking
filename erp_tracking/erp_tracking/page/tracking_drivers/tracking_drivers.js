// Drivers. Traccar defines POST/PUT/DELETE on /drivers, so managers get
// create, edit and delete; everyone else gets a read-only list.
frappe.pages["tracking-drivers"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Drivers"),
		single_column: true,
	});

	const config = await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "drivers",
		filters: [],
		column_overrides: {},
		primary_action: config.can_manage
			? { label: __("New Driver"), action: () => open_driver_dialog(engine) }
			: null,
		on_row_click: (row) => (config.can_manage ? open_driver_dialog(engine, row) : null),
	});

	await engine.setup();
	wrapper.erp_tracking_engine = engine;
};

function open_driver_dialog(engine, driver) {
	const editing = Boolean(driver && driver.id);
	const dialog = new frappe.ui.Dialog({
		title: editing ? __("Edit Driver") : __("New Driver"),
		fields: [
			{ fieldname: "name", label: __("Name"), fieldtype: "Data", reqd: 1, default: driver?.name },
			{
				fieldname: "uniqueId",
				label: __("Unique ID"),
				fieldtype: "Data",
				reqd: 1,
				default: driver?.uniqueId,
			},
		],
		primary_action_label: __("Save"),
		async primary_action(values) {
			const response = await erp_tracking.call("erp_tracking.api.save_driver", {
				payload: JSON.stringify(values),
				driver_id: editing ? driver.id : null,
			});
			if (response.success) {
				dialog.hide();
				frappe.show_alert({ message: __("Driver saved"), indicator: "green" });
				engine.refresh(true);
			}
		},
	});

	if (editing) {
		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete driver {0}?", [driver.name]), async () => {
				const response = await erp_tracking.call("erp_tracking.api.delete_driver", { driver_id: driver.id });
				if (response.success) {
					dialog.hide();
					frappe.show_alert({ message: __("Driver deleted"), indicator: "green" });
					engine.refresh(true);
				}
			});
		});
	}

	dialog.show();
}
