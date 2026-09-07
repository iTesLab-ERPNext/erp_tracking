/**
 * Generic report engine.
 *
 * Filters, request, KPI cards, result table, paging and exports are built from
 * the metadata the backend publishes for each report, so adding a report never
 * means writing another page.
 */
frappe.provide("erp_tracking");

erp_tracking.ReportEngine = class ReportEngine {
	constructor({ page, parent, report, meta, options = {}, on_render = null }) {
		this.page = page;
		this.report = report;
		this.meta = meta;
		this.options = options;
		this.on_render = on_render;

		this.offset = 0;
		this.page_length = (erp_tracking.config && erp_tracking.config.page_length) || 20;

		this.$container = $(`
			<div class="erpt-page">
				<div class="erpt-kpi"></div>
				<div class="erpt-extra"></div>
				<div class="erpt-body"></div>
				<div class="erpt-footer"></div>
			</div>`).appendTo(parent);

		this.$kpi = this.$container.find(".erpt-kpi");
		this.$extra = this.$container.find(".erpt-extra");
		this.$body = this.$container.find(".erpt-body");
		this.$footer = this.$container.find(".erpt-footer");
	}

	async setup() {
		if (await erp_tracking.guard(this.$body)) return;

		this.build_filters();
		this.page.set_primary_action(__("Generate"), () => {
			this.offset = 0;
			this.run();
		});
		this.page.set_secondary_action(__("Refresh"), () => this.run());

		const formats = this.meta.native_download ? ["csv", "xlsx", "pdf"] : ["csv", "pdf"];
		erp_tracking.add_export_menu(this.page, (fmt) => this.export(fmt), formats);
		if (this.meta.native_download) {
			this.page.add_menu_item(__("Send by Email"), () => this.mail());
		}

		this.$body.html(
			erp_tracking.empty_state({
				title: __("Choose your filters"),
				message: __("Select a device or a group and a period, then generate the report."),
			})
		);
	}

	build_filters() {
		this.fields = {};
		const filters = this.meta.filters || [];

		if (filters.includes("deviceId")) {
			this.fields.deviceId = this.page.add_field({
				fieldname: "deviceId",
				label: __("Device"),
				fieldtype: "MultiSelectList",
				get_data: () => this.device_options(),
			});
		}
		if (filters.includes("groupId")) {
			this.fields.groupId = this.page.add_field({
				fieldname: "groupId",
				label: __("Group"),
				fieldtype: "MultiSelectList",
				get_data: () => this.group_options(),
			});
		}
		if (filters.includes("geofenceId")) {
			this.fields.geofenceId = this.page.add_field({
				fieldname: "geofenceId",
				label: __("Geofence"),
				fieldtype: "MultiSelectList",
				get_data: () => this.geofence_options(),
			});
		}
		if (filters.includes("type")) {
			this.fields.type = this.page.add_field({
				fieldname: "type",
				label: __("Event Type"),
				fieldtype: "MultiSelectList",
				get_data: () => this.event_type_options(),
			});
		}

		this.fields.from = this.page.add_field({
			fieldname: "from",
			label: __("From"),
			fieldtype: "Date",
			default: erp_tracking.default_from(),
		});
		this.fields.to = this.page.add_field({
			fieldname: "to",
			label: __("To"),
			fieldtype: "Date",
			default: erp_tracking.default_to(),
		});
		this.fields.from.set_input(erp_tracking.default_from());
		this.fields.to.set_input(erp_tracking.default_to());

		this.load_options();
	}

	async load_options() {
		const include = ["devices", "groups"];
		if (this.fields.geofenceId) include.push("geofences");
		this.options_data = await erp_tracking.filter_options(include);

		if (this.fields.type) {
			const response = await erp_tracking.call("erp_tracking.api.get_notification_types", {}, { silent: true });
			this.event_types = response.data || [];
		}
	}

	device_options() {
		return ((this.options_data && this.options_data.devices) || []).map((d) => ({
			value: String(d.value),
			description: d.label,
		}));
	}

	group_options() {
		return ((this.options_data && this.options_data.groups) || []).map((g) => ({
			value: String(g.value),
			description: g.label,
		}));
	}

	geofence_options() {
		return ((this.options_data && this.options_data.geofences) || []).map((g) => ({
			value: String(g.value),
			description: g.label,
		}));
	}

	event_type_options() {
		return (this.event_types || []).map((t) => ({ value: t.type, description: t.label }));
	}

	current_filters() {
		const filters = {};
		Object.keys(this.fields).forEach((fieldname) => {
			const value = this.fields[fieldname].get_value();
			if (value === undefined || value === null || value === "" || (Array.isArray(value) && !value.length)) return;
			filters[fieldname] = value;
		});
		return filters;
	}

	async run() {
		this.$body.html(`<div class="erpt-loading text-muted">${__("Generating...")}</div>`);

		const response = await erp_tracking.call("erp_tracking.api.run_report", {
			report: this.report,
			filters: JSON.stringify(this.current_filters()),
			limit: this.page_length,
			offset: this.offset,
		});

		if (!response.success) {
			this.$kpi.empty();
			this.$footer.empty();
			this.$body.html(
				erp_tracking.empty_state({
					title: response.message || __("Could not generate the report"),
					message: __("Check the filters and the Traccar connection."),
				})
			);
			return;
		}

		this.render(response.data);
	}

	render(data) {
		const rows = data.items || [];
		erp_tracking.render_cards(this.$kpi, data.kpi || []);

		if (!rows.length) {
			this.$body.html(
				erp_tracking.empty_state({
					title: __("No data for this period"),
					message: __("Try a wider date range or another device."),
				})
			);
			this.$footer.empty();
			if (this.on_render) this.on_render(data);
			return;
		}

		this.$body.empty();
		const $table = $('<div class="erpt-datatable"></div>').appendTo(this.$body);
		new frappe.DataTable($table.get(0), {
			columns: erp_tracking.to_datatable_columns(data.columns, this.options.column_overrides || {}),
			data: rows,
			layout: "fluid",
			noDataMessage: __("No data for this period"),
		});

		erp_tracking.pagination(
			this.$footer,
			{
				offset: data.offset || 0,
				page_length: data.limit || this.page_length,
				count: rows.length,
				total: data.total,
				has_more: (data.offset || 0) + rows.length < data.total,
			},
			(offset) => {
				this.offset = offset;
				this.run();
			}
		);

		if (this.on_render) this.on_render(data);
	}

	export(fmt) {
		erp_tracking.download("erp_tracking.api.export_report", {
			report: this.report,
			filters: this.current_filters(),
			fmt,
		});
	}

	async mail() {
		const response = await erp_tracking.call("erp_tracking.api.mail_report", {
			report: this.report,
			filters: JSON.stringify(this.current_filters()),
		});
		if (response.success) {
			frappe.show_alert({ message: __("Traccar will email the report."), indicator: "green" });
		}
	}
};
