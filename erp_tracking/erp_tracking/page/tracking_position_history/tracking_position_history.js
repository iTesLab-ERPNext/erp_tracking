// Position history for one device over a period: map, table and native exports.
frappe.pages["tracking-position-history"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Position History"),
		single_column: true,
	});
	wrapper.erp_tracking_view = new PositionHistory(page);
	await wrapper.erp_tracking_view.setup();
};

frappe.pages["tracking-position-history"].on_page_show = function (wrapper) {
	const device_id = frappe.get_route()[1];
	if (device_id && wrapper.erp_tracking_view) wrapper.erp_tracking_view.preselect(device_id);
};

class PositionHistory {
	constructor(page) {
		this.page = page;
		this.offset = 0;
		this.page_length = 20;
		this.$container = $(`
			<div class="erpt-page">
				<div class="erpt-map-wrapper" style="height:380px; margin-top:15px"></div>
				<div class="erpt-body"></div>
				<div class="erpt-footer"></div>
			</div>`).appendTo(page.main);
		this.$map = this.$container.find(".erpt-map-wrapper");
		this.$body = this.$container.find(".erpt-body");
		this.$footer = this.$container.find(".erpt-footer");
	}

	async setup() {
		if (await erp_tracking.guard(this.$body)) {
			this.$map.remove();
			return;
		}
		const config = await erp_tracking.get_config();
		this.page_length = config.page_length || 20;

		this.device_field = this.page.add_field({
			fieldname: "device",
			label: __("Device"),
			fieldtype: "Autocomplete",
			reqd: 1,
		});
		this.from_field = this.page.add_field({ fieldname: "from", label: __("From Date"), fieldtype: "Date" });
		this.to_field = this.page.add_field({ fieldname: "to", label: __("To Date"), fieldtype: "Date" });
		this.from_field.set_input(erp_tracking.default_from());
		this.to_field.set_input(erp_tracking.default_to());

		const options = await erp_tracking.filter_options(["devices"]);
		this.device_field.set_data((options.devices || []).map((d) => ({ label: d.label, value: String(d.value) })));

		this.page.set_primary_action(__("Show History"), () => {
			this.offset = 0;
			this.refresh();
		});
		erp_tracking.add_export_menu(this.page, (fmt) => this.export(fmt), ["csv", "xlsx", "pdf", "gpx", "kml"]);

		this.$body.html(
			erp_tracking.empty_state({
				title: __("Choose a device and a period"),
				message: __("Traccar returns the full track for the selected window."),
			})
		);
	}

	preselect(device_id) {
		if (!this.device_field) return;
		this.device_field.set_value(String(device_id));
		this.refresh();
	}

	filters() {
		return {
			device_id: this.device_field.get_value(),
			from_time: this.from_field.get_value(),
			to_time: this.to_field.get_value(),
		};
	}

	async refresh() {
		const filters = this.filters();
		if (!filters.device_id) {
			frappe.show_alert({ message: __("Select a device"), indicator: "orange" });
			return;
		}

		this.$body.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);
		const response = await erp_tracking.call("erp_tracking.api.get_position_history", {
			...filters,
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
		erp_tracking.map.render(this.$map.get(0), { points: rows.slice(0, 200), track: data.track });

		if (!rows.length) {
			this.$body.html(erp_tracking.empty_state({ title: __("No positions in this period") }));
			this.$footer.empty();
			return;
		}

		this.$body.empty();
		const $table = $('<div class="erpt-datatable"></div>').appendTo(this.$body);
		new frappe.DataTable($table.get(0), {
			columns: erp_tracking.to_datatable_columns(
				[
					{ fieldname: "fixTime", label: "Time", fieldtype: "Datetime", width: 165 },
					{ fieldname: "latitude", label: "Latitude", fieldtype: "Float", width: 110 },
					{ fieldname: "longitude", label: "Longitude", fieldtype: "Float", width: 110 },
					{ fieldname: "speed", label: "Speed", fieldtype: "Data", width: 100 },
					{ fieldname: "course", label: "Course", fieldtype: "Float", width: 90 },
					{ fieldname: "altitude", label: "Altitude (m)", fieldtype: "Float", width: 110 },
					{ fieldname: "accuracy", label: "Accuracy (m)", fieldtype: "Float", width: 110 },
					{ fieldname: "address", label: "Address", fieldtype: "Data", width: 280 },
				],
				{ speed: (value) => erp_tracking.format.speed(value) }
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
		if (!filters.device_id) {
			frappe.show_alert({ message: __("Select a device"), indicator: "orange" });
			return;
		}
		erp_tracking.download("erp_tracking.api.export_positions", { ...filters, fmt });
	}
}
