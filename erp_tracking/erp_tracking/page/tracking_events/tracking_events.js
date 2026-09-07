// Events page.
// Traccar has no GET /events collection endpoint, so this page reads
// /reports/events through erp_tracking.api.get_events.
frappe.pages["tracking-events"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Events"),
		single_column: true,
	});
	wrapper.erp_tracking_view = new EventsView(page);
	await wrapper.erp_tracking_view.setup();
};

class EventsView {
	constructor(page) {
		this.page = page;
		this.offset = 0;
		this.page_length = 20;
		this.$container = $(`
			<div class="erpt-page">
				<div class="erpt-body"></div>
				<div class="erpt-footer"></div>
			</div>`).appendTo(page.main);
		this.$body = this.$container.find(".erpt-body");
		this.$footer = this.$container.find(".erpt-footer");
	}

	async setup() {
		if (await erp_tracking.guard(this.$body)) return;
		const config = await erp_tracking.get_config();
		this.page_length = config.page_length || 20;

		this.device_field = this.page.add_field({
			fieldname: "device",
			label: __("Device"),
			fieldtype: "MultiSelectList",
			get_data: () => (this.devices || []).map((d) => ({ value: String(d.value), description: d.label })),
		});
		this.group_field = this.page.add_field({
			fieldname: "group",
			label: __("Group"),
			fieldtype: "MultiSelectList",
			get_data: () => (this.groups || []).map((g) => ({ value: String(g.value), description: g.label })),
		});
		this.type_field = this.page.add_field({
			fieldname: "type",
			label: __("Event Type"),
			fieldtype: "MultiSelectList",
			get_data: () => (this.event_types || []).map((t) => ({ value: t.type, description: t.label })),
		});
		this.from_field = this.page.add_field({ fieldname: "from", label: __("From"), fieldtype: "Date" });
		this.to_field = this.page.add_field({ fieldname: "to", label: __("To"), fieldtype: "Date" });
		this.from_field.set_input(erp_tracking.default_from());
		this.to_field.set_input(erp_tracking.default_to());

		const options = await erp_tracking.filter_options(["devices", "groups"]);
		this.devices = options.devices || [];
		this.groups = options.groups || [];
		const types = await erp_tracking.call("erp_tracking.api.get_notification_types", {}, { silent: true });
		this.event_types = types.data || [];

		this.page.set_primary_action(__("Show Events"), () => {
			this.offset = 0;
			this.refresh();
		});
		this.page.set_secondary_action(__("Refresh"), () => this.refresh());
		erp_tracking.add_export_menu(this.page, (fmt) => this.export(fmt));
		this.page.add_menu_item(__("Open Events Report"), () => frappe.set_route("tracking-reports", "events"));

		await this.refresh();
	}

	filters() {
		return {
			device_ids: this.device_field.get_value() || null,
			group_ids: this.group_field.get_value() || null,
			event_types: this.type_field.get_value() || null,
			from_time: this.from_field.get_value(),
			to_time: this.to_field.get_value(),
		};
	}

	async refresh() {
		this.$body.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);
		const response = await erp_tracking.call("erp_tracking.api.get_events", {
			...this.filters(),
			limit: this.page_length,
			offset: this.offset,
		});

		if (!response.success) {
			this.$body.html(erp_tracking.empty_state({ title: response.message }));
			this.$footer.empty();
			return;
		}

		const data = response.data;
		const rows = data.items || [];
		if (!rows.length) {
			this.$body.html(erp_tracking.empty_state({ title: __("No events in this period") }));
			this.$footer.empty();
			return;
		}

		this.$body.empty();
		const $table = $('<div class="erpt-datatable"></div>').appendTo(this.$body);
		new frappe.DataTable($table.get(0), {
			columns: erp_tracking.to_datatable_columns(
				[
					{ fieldname: "eventTime", label: "Date", fieldtype: "Datetime", width: 165 },
					{ fieldname: "deviceName", label: "Device", fieldtype: "Data", width: 160 },
					{ fieldname: "type", label: "Event Type", fieldtype: "Data", width: 170 },
					{ fieldname: "positionId", label: "Position", fieldtype: "Int", width: 100 },
					{ fieldname: "geofenceId", label: "Geofence", fieldtype: "Int", width: 100 },
					{ fieldname: "attributes", label: "Attributes", fieldtype: "Data", width: 300 },
				],
				{ type: (value, row) => erp_tracking.format.event_badge(value, row.badge) }
			),
			data: rows,
			layout: "fluid",
		});

		erp_tracking.pagination(
			this.$footer,
			{
				offset: data.offset,
				page_length: data.limit || this.page_length,
				count: rows.length,
				total: data.total,
				has_more: data.offset + rows.length < data.total,
			},
			(offset) => {
				this.offset = offset;
				this.refresh();
			}
		);
	}

	export(fmt) {
		const filters = this.filters();
		erp_tracking.download("erp_tracking.api.export_report", {
			report: "events",
			fmt,
			filters: {
				deviceId: filters.device_ids,
				groupId: filters.group_ids,
				type: filters.event_types,
				from: filters.from_time,
				to: filters.to_time,
			},
		});
	}
}
