// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// Note: the Traccar Calendar schema only has {id, name, data, attributes} -
// "data" is base64-encoded iCalendar text. There is no separate "Schedule"
// or "Timezone" field on the wire (see calendars.py docstring), so this
// page shows a decoded preview of `data` instead of inventing columns the
// API doesn't return.

frappe.pages["erp-tracking-calendars"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Calendars"),
		single_column: true,
	});

	page.set_primary_action(__("New Calendar"), () => show_calendar_dialog(null, () => list.load({ refresh: true })), "fa fa-plus");

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_calendars",
		page_length: 20,
		columns: [
			{ label: __("Name"), field: "name" },
			{
				label: __("Schedule Preview"),
				field: "data",
				format: (v) => {
					if (!v) return "—";
					try {
						const decoded = atob(v);
						return `<code>${frappe.utils.escape_html(decoded.slice(0, 80))}${decoded.length > 80 ? "…" : ""}</code>`;
					} catch (e) {
						return "—";
					}
				},
			},
		],
		on_row_click: (row) => show_calendar_dialog(row, () => list.load({ refresh: true })),
	});
	list.load();
};

function show_calendar_dialog(calendar, on_done) {
	const is_new = !calendar;
	let decoded_data = "";
	if (calendar && calendar.data) {
		try {
			decoded_data = atob(calendar.data);
		} catch (e) {
			decoded_data = "";
		}
	}

	const dialog = new frappe.ui.Dialog({
		title: is_new ? __("New Calendar") : __("Edit Calendar"),
		fields: [
			{ fieldtype: "Data", fieldname: "name", label: __("Name"), reqd: 1 },
			{
				fieldtype: "Code",
				fieldname: "ical_data",
				label: __("iCalendar Data"),
				reqd: 1,
				description: __("Raw iCalendar text (BEGIN:VCALENDAR ... END:VCALENDAR). Base64-encoded automatically before sending to Traccar."),
			},
		],
		primary_action_label: is_new ? __("Create") : __("Save"),
		primary_action: (values) => {
			dialog.disable_primary_action();
			const method = is_new ? "erp_tracking.api.create_calendar" : "erp_tracking.api.update_calendar";
			const args = is_new
				? { name: values.name, ical_data: values.ical_data }
				: { calendar_id: calendar.id, name: values.name, ical_data: values.ical_data };

			frappe.call({
				method,
				args,
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: is_new ? __("Calendar created.") : __("Calendar updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to save calendar."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	if (!is_new) {
		dialog.set_values({ name: calendar.name, ical_data: decoded_data });

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete calendar {0}?", [calendar.name]), () => {
				frappe.call({
					method: "erp_tracking.api.delete_calendar",
					args: { calendar_id: calendar.id },
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: __("Calendar deleted."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to delete calendar."));
						}
					},
				});
			});
		});
	} else {
		dialog.set_value(
			"ical_data",
			"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:Active Hours\nDTSTART:20260101T080000Z\nDTEND:20260101T180000Z\nRRULE:FREQ=DAILY\nEND:VEVENT\nEND:VCALENDAR"
		);
	}

	dialog.show();
}
