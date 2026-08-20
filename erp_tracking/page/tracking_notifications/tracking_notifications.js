// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-notifications"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Notifications"),
		single_column: true,
	});

	page.add_menu_item(__("Send Test Notification"), () => {
		frappe.call({
			method: "erp_tracking.api.send_test_notification",
			freeze: true,
			callback: (r) => {
				const result = r.message || {};
				frappe.show_alert({
					message: result.success ? __("Test notification sent.") : (result.message || __("Failed to send.")),
					indicator: result.success ? "green" : "red",
				});
			},
		});
	});

	page.set_primary_action(__("New Notification"), () => show_notification_dialog(null, () => list.load({ refresh: true })), "fa fa-plus");

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_notifications",
		page_length: 20,
		columns: [
			{ label: __("Type"), field: "type" },
			{ label: __("Description"), field: "description", format: (v) => v || "—" },
			{ label: __("Calendar"), field: "calendarId", format: (v) => v || "—" },
			{ label: __("Notificators"), field: "notificators", format: (v) => v || "—" },
			{
				label: __("Disabled"),
				field: "always",
				format: (v) => (v ? `<span class="indicator-pill success">${__("Always")}</span>` : `<span class="indicator-pill">${__("Scheduled")}</span>`),
			},
		],
		on_row_click: (row) => show_notification_dialog(row, () => list.load({ refresh: true })),
	});
	list.load();
};

function show_notification_dialog(notification, on_done) {
	const is_new = !notification;

	frappe.call({
		method: "erp_tracking.api.get_notification_types",
		callback: (r1) => {
			const types = (r1.message && r1.message.success && r1.message.data) || [];
			frappe.call({
				method: "erp_tracking.api.get_notificators",
				callback: (r2) => {
					const notificators = (r2.message && r2.message.success && r2.message.data) || [];
					render_dialog(types, notificators);
				},
			});
		},
	});

	function render_dialog(types, notificators) {
		const dialog = new frappe.ui.Dialog({
			title: is_new ? __("New Notification") : __("Edit Notification"),
			fields: [
				{
					fieldtype: "Select",
					fieldname: "type_",
					label: __("Type"),
					reqd: 1,
					options: types.map((t) => t.type).join("\n"),
				},
				{
					fieldtype: "MultiSelectPills",
					fieldname: "notificators",
					label: __("Notificators"),
					reqd: 1,
					get_data: () => notificators.map((n) => ({ value: n.type, label: n.type })),
				},
				{ fieldtype: "Small Text", fieldname: "description", label: __("Description") },
				{ fieldtype: "Check", fieldname: "always", label: __("Always (ignore calendar schedule)") },
				{ fieldtype: "Int", fieldname: "calendar_id", label: __("Calendar ID") },
			],
			primary_action_label: is_new ? __("Create") : __("Save"),
			primary_action: (values) => {
				dialog.disable_primary_action();
				const notificators_value = Array.isArray(values.notificators) ? values.notificators.join(",") : values.notificators;
				const method = is_new ? "erp_tracking.api.create_notification" : "erp_tracking.api.update_notification";
				const args = is_new
					? { type_: values.type_, notificators: notificators_value, description: values.description, always: values.always, calendar_id: values.calendar_id }
					: { notification_id: notification.id, type: values.type_, notificators: notificators_value, description: values.description, always: values.always, calendarId: values.calendar_id };

				frappe.call({
					method,
					args,
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: is_new ? __("Notification created.") : __("Notification updated."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to save notification."));
						}
						dialog.enable_primary_action();
					},
					error: () => dialog.enable_primary_action(),
				});
			},
		});

		if (!is_new) {
			dialog.set_values({
				type_: notification.type,
				notificators: (notification.notificators || "").split(",").filter(Boolean),
				description: notification.description,
				always: notification.always,
				calendar_id: notification.calendarId,
			});

			dialog.set_secondary_action_label(__("Delete"));
			dialog.set_secondary_action(() => {
				frappe.confirm(__("Delete this notification rule?"), () => {
					frappe.call({
						method: "erp_tracking.api.delete_notification",
						args: { notification_id: notification.id },
						callback: (r) => {
							const result = r.message || {};
							if (result.success) {
								frappe.show_alert({ message: __("Notification deleted."), indicator: "green" });
								dialog.hide();
								on_done && on_done();
							} else {
								frappe.msgprint(result.message || __("Unable to delete notification."));
							}
						},
					});
				});
			});
		}

		dialog.show();
	}
}
