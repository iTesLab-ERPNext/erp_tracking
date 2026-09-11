// Calendars. Traccar defines POST/PUT/DELETE on /calendars, so managers get
// create, edit and delete; everyone else gets a read-only list. The list
// row (and even get_calendar's raw payload) never carries the raw base64
// iCalendar blob - editing fetches erp_tracking.api.get_calendar first,
// which additionally decodes it into a plain-text `ical_text` field just
// for this purpose (see calendars.py).
frappe.pages["tracking-calendars"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Calendars"),
		single_column: true,
	});

	const config = await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "calendars",
		filters: [],
		column_overrides: {},
		primary_action: config.can_manage
			? { label: __("New Calendar"), action: () => open_calendar_dialog(engine) }
			: null,
		on_row_click: (row) => (config.can_manage ? edit_calendar(engine, row) : null),
	});

	await engine.setup();
	wrapper.erp_tracking_engine = engine;
};

async function edit_calendar(engine, row) {
	frappe.show_alert({ message: __("Loading schedule..."), indicator: "blue" });
	const response = await erp_tracking.call("erp_tracking.api.get_calendar", { calendar_id: row.id });
	if (!response.success) {
		frappe.msgprint(response.message);
		return;
	}
	open_calendar_dialog(engine, response.data);
}

const ICAL_TEMPLATE =
	"BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nSUMMARY:Active Hours\nDTSTART:20260101T080000Z\nDTEND:20260101T180000Z\nRRULE:FREQ=DAILY\nEND:VEVENT\nEND:VCALENDAR";

function open_calendar_dialog(engine, calendar) {
	const editing = Boolean(calendar && calendar.id);
	const dialog = new frappe.ui.Dialog({
		title: editing ? __("Edit Calendar") : __("New Calendar"),
		fields: [
			{ fieldname: "name", label: __("Name"), fieldtype: "Data", reqd: 1, default: calendar?.name },
			{
				fieldname: "ical_text",
				label: __("Schedule (iCalendar)"),
				fieldtype: "Code",
				options: "Text",
				reqd: 1,
				default: editing ? calendar?.ical_text : ICAL_TEMPLATE,
				description: __("Raw iCalendar text (BEGIN:VCALENDAR ... END:VCALENDAR). Encoded automatically before it is sent to Traccar."),
			},
		],
		primary_action_label: __("Save"),
		async primary_action(values) {
			const response = await erp_tracking.call("erp_tracking.api.save_calendar", {
				payload: JSON.stringify(values),
				calendar_id: editing ? calendar.id : null,
			});
			if (response.success) {
				dialog.hide();
				frappe.show_alert({ message: __("Calendar saved"), indicator: "green" });
				engine.refresh(true);
			}
		},
	});

	if (editing) {
		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete calendar {0}?", [calendar.name]), async () => {
				const response = await erp_tracking.call("erp_tracking.api.delete_calendar", {
					calendar_id: calendar.id,
				});
				if (response.success) {
					dialog.hide();
					frappe.show_alert({ message: __("Calendar deleted"), indicator: "green" });
					engine.refresh(true);
				}
			});
		});
	}

	dialog.show();
}
