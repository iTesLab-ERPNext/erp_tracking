// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-commands"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Commands"),
		single_column: true,
	});

	page.set_primary_action(__("Send Command"), () => show_send_command_dialog(), "fa fa-paper-plane");
	page.add_menu_item(__("New Saved Command"), () => show_saved_command_dialog(null, () => list.load({ refresh: true })));

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_commands",
		page_length: 20,
		columns: [
			{ label: __("Description"), field: "description" },
			{ label: __("Type"), field: "type" },
			{ label: __("Device"), field: "deviceId", format: (v) => (v ? `#${v}` : __("Any")) },
			{
				label: __("Channel"),
				field: "textChannel",
				format: (v) => (v ? __("SMS") : __("Data")),
			},
		],
		on_row_click: (row) => show_saved_command_dialog(row, () => list.load({ refresh: true })),
	});
	list.load();
};

function show_saved_command_dialog(command, on_done) {
	const is_new = !command;

	const dialog = new frappe.ui.Dialog({
		title: is_new ? __("New Saved Command") : __("Edit Saved Command"),
		fields: [
			{ fieldtype: "Data", fieldname: "description", label: __("Description"), reqd: 1 },
			{ fieldtype: "Data", fieldname: "type_", label: __("Command Type"), reqd: 1 },
			{ fieldtype: "Int", fieldname: "device_id", label: __("Device ID (blank = any)") },
			{ fieldtype: "Check", fieldname: "text_channel", label: __("Send via SMS") },
			{ fieldtype: "Code", fieldname: "attributes", label: __("Attributes (JSON)"), options: "JSON" },
		],
		primary_action_label: is_new ? __("Create") : __("Save"),
		primary_action: (values) => {
			let attributes = null;
			if (values.attributes) {
				try {
					attributes = JSON.parse(values.attributes);
				} catch (e) {
					frappe.msgprint(__("Attributes must be valid JSON."));
					return;
				}
			}

			dialog.disable_primary_action();
			const method = is_new ? "erp_tracking.api.create_saved_command" : "erp_tracking.api.update_saved_command";
			const args = is_new
				? { device_id: values.device_id, description: values.description, type_: values.type_, text_channel: values.text_channel, attributes: attributes ? JSON.stringify(attributes) : undefined }
				: { command_id: command.id, deviceId: values.device_id, description: values.description, type: values.type_, textChannel: values.text_channel, attributes };

			frappe.call({
				method,
				args,
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: is_new ? __("Saved command created.") : __("Saved command updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to save."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	if (!is_new) {
		dialog.set_values({
			description: command.description,
			type_: command.type,
			device_id: command.deviceId,
			text_channel: command.textChannel,
			attributes: command.attributes ? JSON.stringify(command.attributes, null, 2) : "",
		});

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete this saved command?"), () => {
				frappe.call({
					method: "erp_tracking.api.delete_saved_command",
					args: { command_id: command.id },
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: __("Saved command deleted."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to delete."));
						}
					},
				});
			});
		});
	}

	dialog.show();
}

function show_send_command_dialog() {
	frappe.call({
		method: "erp_tracking.api.get_devices",
		args: { limit: 500 },
		callback: (r) => {
			const devices = (r.message && r.message.success && r.message.data) || [];
			render_send_dialog(devices);
		},
	});

	function render_send_dialog(devices) {
		const dialog = new frappe.ui.Dialog({
			title: __("Send Command"),
			fields: [
				{
					fieldtype: "Select",
					fieldname: "device_id",
					label: __("Device"),
					reqd: 1,
					options: devices.map((d) => `${d.id}:::${d.name}`).join("\n"),
					// Dialog Select fields need "value:label"-style rendering; we
					// encode both in the option and parse back on submit.
				},
				{
					fieldtype: "Select",
					fieldname: "type_",
					label: __("Command Type"),
					reqd: 1,
					description: __("Populated once a device is selected, based on that device's supported protocol commands."),
				},
				{ fieldtype: "Check", fieldname: "text_channel", label: __("Send via SMS") },
				{ fieldtype: "Code", fieldname: "attributes", label: __("Attributes (JSON)"), options: "JSON" },
			],
			primary_action_label: __("Send"),
			primary_action: (values) => {
				let attributes = null;
				if (values.attributes) {
					try {
						attributes = JSON.parse(values.attributes);
					} catch (e) {
						frappe.msgprint(__("Attributes must be valid JSON."));
						return;
					}
				}

				const device_id = (values.device_id || "").split(":::")[0];
				dialog.disable_primary_action();

				frappe.call({
					method: "erp_tracking.api.send_command",
					args: {
						device_id,
						type_: values.type_,
						text_channel: values.text_channel,
						attributes: attributes ? JSON.stringify(attributes) : undefined,
					},
					callback: (r) => {
						const result = r.message || {};
						dialog.enable_primary_action();
						if (!result.success) {
							frappe.msgprint(`🔴 ${frappe.utils.escape_html(result.message || __("Failed to send command."))}`);
							return;
						}
						const sent = result.status_code === 200;
						frappe.show_alert({
							message: sent ? __("🟢 Command sent") : __("🟠 Command queued"),
							indicator: sent ? "green" : "orange",
						});
						dialog.hide();
					},
					error: () => dialog.enable_primary_action(),
				});
			},
		});

		dialog.fields_dict.device_id.df.change = () => {
			const device_id = (dialog.get_value("device_id") || "").split(":::")[0];
			if (!device_id) return;

			frappe.call({
				method: "erp_tracking.api.get_command_types",
				args: { device_id },
				callback: (r) => {
					const result = r.message || {};
					const types = result.success ? result.data || [] : [];
					dialog.set_df_property("type_", "options", types.map((t) => t.type).join("\n"));
					dialog.refresh_field("type_");
					if (!types.length) {
						frappe.show_alert({ message: __("No command types available for this device."), indicator: "orange" });
					}
				},
			});
		};

		dialog.show();
	}
}
