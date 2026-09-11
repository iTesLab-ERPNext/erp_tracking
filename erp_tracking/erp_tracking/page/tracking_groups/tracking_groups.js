// Groups. Traccar defines POST/PUT/DELETE on /groups, so managers get
// create, edit and delete; everyone else gets a read-only list.
frappe.pages["tracking-groups"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Groups"),
		single_column: true,
	});

	const config = await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "groups",
		filters: [],
		column_overrides: {},
		primary_action: config.can_manage
			? { label: __("New Group"), action: () => open_group_dialog(engine) }
			: null,
		on_row_click: (row) => (config.can_manage ? open_group_dialog(engine, row) : null),
	});

	await engine.setup();
	wrapper.erp_tracking_engine = engine;
};

function open_group_dialog(engine, group) {
	const editing = Boolean(group && group.id);
	const dialog = new frappe.ui.Dialog({
		title: editing ? __("Edit Group") : __("New Group"),
		fields: [
			{ fieldname: "name", label: __("Name"), fieldtype: "Data", reqd: 1, default: group?.name },
			{
				fieldname: "groupId",
				label: __("Parent Group ID"),
				fieldtype: "Int",
				default: group?.groupId,
				description: __("Leave blank for a top-level group."),
			},
			...(editing ? [{ fieldname: "view_devices_html", fieldtype: "HTML" }] : []),
		],
		primary_action_label: __("Save"),
		async primary_action(values) {
			const response = await erp_tracking.call("erp_tracking.api.save_group", {
				payload: JSON.stringify(values),
				group_id: editing ? group.id : null,
			});
			if (response.success) {
				dialog.hide();
				frappe.show_alert({ message: __("Group saved"), indicator: "green" });
				engine.refresh(true);
			}
		},
	});

	if (editing) {
		dialog.fields_dict.view_devices_html.$wrapper.html(
			`<button class="btn btn-default btn-sm" data-view-devices>${__("View Devices in Group")}</button>`
		);
		dialog.fields_dict.view_devices_html.$wrapper
			.find("[data-view-devices]")
			.on("click", () => open_group_devices(group));

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete group {0}?", [group.name]), async () => {
				const response = await erp_tracking.call("erp_tracking.api.delete_group", { group_id: group.id });
				if (response.success) {
					dialog.hide();
					frappe.show_alert({ message: __("Group deleted"), indicator: "green" });
					engine.refresh(true);
				}
			});
		});
	}

	dialog.show();
}

async function open_group_devices(group) {
	const response = await erp_tracking.call("erp_tracking.api.get_group_devices", { group_id: group.id });
	const devices = response.success ? response.data || [] : [];

	const dialog = new frappe.ui.Dialog({
		title: __("Devices in {0}", [group.name]),
		fields: [{ fieldname: "list_html", fieldtype: "HTML" }],
	});

	if (!devices.length) {
		dialog.fields_dict.list_html.$wrapper.html(
			erp_tracking.empty_state({ title: __("No devices in this group") })
		);
	} else {
		const $table = $('<div class="erpt-datatable"></div>').appendTo(dialog.fields_dict.list_html.$wrapper);
		new frappe.DataTable($table.get(0), {
			columns: [
				{ id: "name", name: __("Name"), width: 200 },
				{ id: "status", name: __("Status"), width: 120 },
			],
			data: devices,
			layout: "fluid",
		});
	}

	dialog.show();
}
