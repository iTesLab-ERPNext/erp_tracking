// Saved commands, command types and dispatch. Manager-only page.
frappe.pages["tracking-commands"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Commands"),
		single_column: true,
	});

	await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "commands",
		filters: [{ fieldname: "deviceId", label: __("Device"), fieldtype: "Autocomplete", source: "devices" }],
		primary_action: {
			label: __("Send Command"),
			action: () => erp_tracking.send_command_dialog({ on_success: () => engine.refresh(true) }),
		},
		on_row_click: (row) => erp_tracking.send_command_dialog({ saved_command: row }),
	});

	await engine.setup();
	page.add_menu_item(__("New Saved Command"), () => open_saved_command_dialog(engine));
	page.add_menu_item(__("Command Types"), () => show_command_types());
	wrapper.erp_tracking_engine = engine;
};

async function show_command_types() {
	const dialog = new frappe.ui.Dialog({
		title: __("Command Types"),
		fields: [
			{
				fieldname: "device",
				label: __("Device"),
				fieldtype: "Autocomplete",
				description: __("Leave empty to list every command type the server supports."),
			},
			{ fieldname: "text_channel", label: __("SMS commands"), fieldtype: "Check" },
			{ fieldname: "types", fieldtype: "HTML" },
		],
	});
	dialog.show();

	const options = await erp_tracking.filter_options(["devices"]);
	dialog.fields_dict.device.set_data(
		(options.devices || []).map((d) => ({ label: d.label, value: String(d.value) }))
	);

	const load = async () => {
		const response = await erp_tracking.call("erp_tracking.api.get_command_types", {
			device_id: dialog.get_value("device") || null,
			text_channel: dialog.get_value("text_channel") ? 1 : 0,
		});
		const types = response.data || [];
		dialog.fields_dict.types.$wrapper.html(
			types.length
				? `<ul>${types.map((t) => `<li>${frappe.utils.escape_html(t.label)} <span class="text-muted">(${frappe.utils.escape_html(t.type)})</span></li>`).join("")}</ul>`
				: erp_tracking.empty_state({ title: __("No command types available") })
		);
	};

	dialog.fields_dict.device.df.change = load;
	dialog.fields_dict.text_channel.df.change = load;
	load();
}

function open_saved_command_dialog(engine, command) {
	const editing = Boolean(command && command.id);
	const dialog = new frappe.ui.Dialog({
		title: editing ? __("Edit Saved Command") : __("New Saved Command"),
		fields: [
			{ fieldname: "description", label: __("Description"), fieldtype: "Data", default: command?.description },
			{ fieldname: "type", label: __("Command Type"), fieldtype: "Data", reqd: 1, default: command?.type },
			{ fieldname: "deviceId", label: __("Device ID"), fieldtype: "Int", default: command?.deviceId },
			{ fieldname: "textChannel", label: __("Send by SMS"), fieldtype: "Check", default: command?.textChannel },
			{
				fieldname: "attributes",
				label: __("Parameters (JSON)"),
				fieldtype: "Code",
				options: "JSON",
				default: command?.attributes || "{}",
			},
		],
		primary_action_label: __("Save"),
		async primary_action(values) {
			let attributes = {};
			try {
				attributes = JSON.parse(values.attributes || "{}");
			} catch (error) {
				frappe.msgprint(__("Parameters must be valid JSON."));
				return;
			}
			const response = await erp_tracking.call("erp_tracking.api.save_command", {
				payload: JSON.stringify({ ...values, attributes }),
				command_id: editing ? command.id : null,
			});
			if (response.success) {
				dialog.hide();
				frappe.show_alert({ message: __("Saved command stored"), indicator: "green" });
				engine.refresh(true);
			}
		},
	});
	dialog.show();
}

/** Shared Send Command dialog, also used from the device detail page. */
erp_tracking.send_command_dialog = async function ({ device_id = null, saved_command = null, on_success = null } = {}) {
	const dialog = new frappe.ui.Dialog({
		title: __("Send Command"),
		fields: [
			{ fieldname: "device", label: __("Device"), fieldtype: "Autocomplete", reqd: 1, default: device_id ? String(device_id) : "" },
			{
				fieldname: "command_type",
				label: __("Command Type"),
				fieldtype: "Autocomplete",
				reqd: !saved_command,
				read_only: Boolean(saved_command),
				default: saved_command?.type,
			},
			{ fieldname: "text_channel", label: __("Send by SMS"), fieldtype: "Check" },
			{
				fieldname: "attributes",
				label: __("Parameters (JSON)"),
				fieldtype: "Code",
				options: "JSON",
				default: saved_command?.attributes || "{}",
			},
		],
		primary_action_label: __("Send Command"),
		async primary_action(values) {
			let attributes = {};
			try {
				attributes = JSON.parse(values.attributes || "{}");
			} catch (error) {
				frappe.msgprint(__("Parameters must be valid JSON."));
				return;
			}

			const response = await erp_tracking.call(
				"erp_tracking.api.send_command",
				{
					device_id: values.device,
					command_type: saved_command ? null : values.command_type,
					saved_command_id: saved_command ? saved_command.id : null,
					attributes: JSON.stringify(attributes),
					text_channel: values.text_channel ? 1 : 0,
				},
				{ freeze: true, freeze_message: __("Sending command...") }
			);

			if (!response.success) return;

			dialog.hide();
			const queued = response.data && response.data.queued;
			frappe.msgprint({
				title: queued ? __("Command queued") : __("Command sent"),
				indicator: queued ? "orange" : "green",
				message: queued
					? __("The device is offline. Traccar will deliver the command when it reconnects.")
					: __("Traccar delivered the command to the device."),
			});
			if (on_success) on_success();
		},
	});

	dialog.show();

	const options = await erp_tracking.filter_options(["devices"]);
	dialog.fields_dict.device.set_data(
		(options.devices || []).map((d) => ({ label: d.label, value: String(d.value) }))
	);

	if (!saved_command) {
		const load_types = async () => {
			const response = await erp_tracking.call("erp_tracking.api.get_command_types", {
				device_id: dialog.get_value("device") || null,
				text_channel: dialog.get_value("text_channel") ? 1 : 0,
			});
			dialog.fields_dict.command_type.set_data(
				(response.data || []).map((t) => ({ label: t.label, value: t.type }))
			);
		};
		dialog.fields_dict.device.df.change = load_types;
		dialog.fields_dict.text_channel.df.change = load_types;
		load_types();
	}
};
