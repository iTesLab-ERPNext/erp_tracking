// Devices list. Clicking a row opens the device detail page (view details).
// Create is a dialog on this page; Edit/Delete live on the detail page
// itself (see tracking_device_detail.js) since that is already the "view
// details" surface - erp_tracking.open_device_dialog is shared by both.
frappe.pages["tracking-devices"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Devices"),
		single_column: true,
	});

	const config = await erp_tracking.get_config();

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
		primary_action: config.can_manage
			? { label: __("New Device"), action: () => erp_tracking.open_device_dialog(null, () => engine.refresh(true)) }
			: null,
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

/**
 * Shared Create/Edit dialog for a Device - used by this list page (Create)
 * and by the Device Detail page (Edit), so there is exactly one place that
 * builds the Device form.
 */
erp_tracking.open_device_dialog = function (device, on_saved) {
	const editing = Boolean(device && device.id);
	const dialog = new frappe.ui.Dialog({
		title: editing ? __("Edit Device") : __("New Device"),
		fields: [
			{ fieldname: "name", label: __("Name"), fieldtype: "Data", reqd: 1, default: device?.name },
			{
				fieldname: "uniqueId",
				label: __("Unique ID"),
				fieldtype: "Data",
				reqd: 1,
				default: device?.uniqueId,
			},
			{ fieldname: "column_break_1", fieldtype: "Column Break" },
			{ fieldname: "category", label: __("Category"), fieldtype: "Data", default: device?.category },
			{ fieldname: "model", label: __("Model"), fieldtype: "Data", default: device?.model },
			{ fieldname: "section_break_1", fieldtype: "Section Break" },
			{ fieldname: "phone", label: __("Phone"), fieldtype: "Data", default: device?.phone },
			{ fieldname: "contact", label: __("Contact"), fieldtype: "Data", default: device?.contact },
			{ fieldname: "column_break_2", fieldtype: "Column Break" },
			{ fieldname: "groupId", label: __("Group ID"), fieldtype: "Int", default: device?.groupId },
			{ fieldname: "disabled", label: __("Disabled"), fieldtype: "Check", default: device?.disabled ? 1 : 0 },
		],
		primary_action_label: __("Save"),
		async primary_action(values) {
			const response = await erp_tracking.call("erp_tracking.api.save_device", {
				payload: JSON.stringify(values),
				device_id: editing ? device.id : null,
			});
			if (response.success) {
				dialog.hide();
				frappe.show_alert({ message: __("Device saved"), indicator: "green" });
				if (on_saved) on_saved(response.data);
			}
		},
	});

	if (editing) {
		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete device {0}? This cannot be undone.", [device.name]), async () => {
				const response = await erp_tracking.call("erp_tracking.api.delete_device", { device_id: device.id });
				if (response.success) {
					dialog.hide();
					frappe.show_alert({ message: __("Device deleted"), indicator: "green" });
					if (on_saved) on_saved(null, true);
				}
			});
		});
	}

	dialog.show();
};
