/**
 * Generic list engine.
 *
 * Every collection page (devices, groups, drivers, geofences, ...) is one
 * instance of this class. Search, paging, sorting, refresh and export are
 * implemented once here.
 */
frappe.provide("erp_tracking");

erp_tracking.ListEngine = class ListEngine {
	constructor({
		page,
		parent,
		resource,
		filters = [],
		column_overrides = {},
		on_row_click = null,
		export_formats = ["csv", "xlsx", "pdf"],
		primary_action = null,
	}) {
		this.page = page;
		this.resource = resource;
		this.filter_defs = filters;
		this.column_overrides = column_overrides;
		this.on_row_click = on_row_click;
		this.export_formats = export_formats;
		this.primary_action = primary_action;

		this.offset = 0;
		this.page_length = (erp_tracking.config && erp_tracking.config.page_length) || 20;
		this.sort_by = null;
		this.sort_order = "asc";

		this.$container = $(`
			<div class="erpt-page">
				<div class="erpt-body"></div>
				<div class="erpt-footer"></div>
			</div>`).appendTo(parent);

		this.$body = this.$container.find(".erpt-body");
		this.$footer = this.$container.find(".erpt-footer");
	}

	async setup() {
		if (await erp_tracking.guard(this.$body)) return;

		this.build_filters();
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(true));
		erp_tracking.add_export_menu(this.page, (fmt) => this.export(fmt), this.export_formats);

		if (this.primary_action) {
			this.page.set_primary_action(this.primary_action.label, this.primary_action.action, "add");
		}

		await this.refresh();
	}

	build_filters() {
		this.fields = {};

		this.fields.keyword = this.page.add_field({
			fieldname: "keyword",
			label: __("Search"),
			fieldtype: "Data",
			change: () => this.reset_and_refresh(),
		});

		this.filter_defs.forEach((definition) => {
			const { source, ...df } = definition;
			this.fields[definition.fieldname] = this.page.add_field({
				...df,
				change: () => this.reset_and_refresh(),
			});
			if (source) this.load_choices(definition.fieldname, source);
		});
	}

	/** Populate an Autocomplete filter from the Traccar device/group lists. */
	async load_choices(fieldname, source) {
		const options = await erp_tracking.filter_options([source]);
		const choices = (options[source] || []).map((item) => ({
			label: item.label,
			value: String(item.value),
		}));
		const field = this.fields[fieldname];
		if (field && field.set_data) field.set_data(choices);
	}

	reset_and_refresh() {
		this.offset = 0;
		this.refresh();
	}

	current_filters() {
		const filters = { limit: this.page_length, offset: this.offset };
		Object.keys(this.fields).forEach((fieldname) => {
			const value = this.fields[fieldname].get_value();
			if (value !== undefined && value !== null && value !== "") filters[fieldname] = value;
		});
		if (this.sort_by) {
			filters.sort_by = this.sort_by;
			filters.sort_order = this.sort_order;
		}
		return filters;
	}

	async refresh(force = false) {
		this.$body.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);

		const response = await erp_tracking.call("erp_tracking.api.get_list", {
			resource: this.resource,
			filters: JSON.stringify(this.current_filters()),
			refresh: force ? 1 : 0,
		});

		if (!response.success) {
			this.$body.html(
				erp_tracking.empty_state({
					title: response.message || __("Could not load data"),
					message: __("Check the Traccar connection, then try again."),
				})
			);
			this.$footer.empty();
			return;
		}

		this.render(response.data);
	}

	render(data) {
		const rows = data.items || [];
		if (!rows.length) {
			this.$body.html(
				erp_tracking.empty_state({
					title: __("No records found"),
					message: __("Adjust the filters or the search term."),
				})
			);
			this.$footer.empty();
			return;
		}

		this.$body.empty();
		const $table = $('<div class="erpt-datatable"></div>').appendTo(this.$body);

		this.datatable = new frappe.DataTable($table.get(0), {
			columns: erp_tracking.to_datatable_columns(data.columns, this.column_overrides),
			data: rows,
			layout: "fluid",
			inlineFilters: false,
			noDataMessage: __("No records found"),
			events: {
				onSortColumn: (column, direction) => {
					this.sort_by = column.id;
					this.sort_order = direction === "desc" ? "desc" : "asc";
					this.refresh();
				},
			},
		});

		if (this.on_row_click) {
			$table.on("click", ".dt-cell", (event) => {
				const index = $(event.currentTarget).attr("data-row-index");
				if (index !== undefined) this.on_row_click(rows[Number(index)]);
			});
		}

		erp_tracking.pagination(
			this.$footer,
			{
				offset: data.offset || 0,
				page_length: data.page_length || this.page_length,
				count: rows.length,
				has_more: data.has_more,
			},
			(offset) => {
				this.offset = offset;
				this.refresh();
			}
		);
	}

	export(fmt) {
		const filters = this.current_filters();
		delete filters.limit;
		delete filters.offset;
		erp_tracking.download("erp_tracking.api.export_list", {
			resource: this.resource,
			filters,
			fmt,
		});
	}
};
