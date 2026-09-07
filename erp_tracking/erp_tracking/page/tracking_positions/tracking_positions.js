// Live positions: last known position per device, with map and export.
frappe.pages["tracking-positions"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Live Positions"),
		single_column: true,
	});
	wrapper.erp_tracking_view = new LivePositions(page);
	await wrapper.erp_tracking_view.setup();
};

class LivePositions {
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
			change: () => this.reload(),
		});
		this.group_field = this.page.add_field({
			fieldname: "group",
			label: __("Group"),
			fieldtype: "Autocomplete",
			change: () => this.reload(),
		});
		this.status_field = this.page.add_field({
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: [
				{ value: "", label: __("All statuses") },
				{ value: "online", label: __("Online") },
				{ value: "offline", label: __("Offline") },
				{ value: "unknown", label: __("Unknown") },
			],
			change: () => this.reload(),
		});

		const options = await erp_tracking.filter_options(["devices", "groups"]);
		this.device_field.set_data((options.devices || []).map((d) => ({ label: d.label, value: String(d.value) })));
		this.group_field.set_data((options.groups || []).map((g) => ({ label: g.label, value: String(g.value) })));

		this.page.set_secondary_action(__("Refresh"), () => this.refresh());
		erp_tracking.add_export_menu(this.page, (fmt) => this.export(fmt));

		await this.refresh();
	}

	filters() {
		return {
			device_ids: this.device_field.get_value() || null,
			group_id: this.group_field.get_value() || null,
			status: this.status_field.get_value() || null,
		};
	}

	reload() {
		this.offset = 0;
		this.refresh();
	}

	async refresh() {
		this.$body.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);
		const response = await erp_tracking.call("erp_tracking.api.get_live_positions", {
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
		erp_tracking.map.render(this.$map.get(0), { points: rows });

		if (!rows.length) {
			this.$body.html(erp_tracking.empty_state({ title: __("No positions reported") }));
			this.$footer.empty();
			return;
		}

		this.$body.empty();
		const $table = $('<div class="erpt-datatable"></div>').appendTo(this.$body);
		new frappe.DataTable($table.get(0), {
			columns: erp_tracking.to_datatable_columns(
				[
					{ fieldname: "deviceName", label: "Device", fieldtype: "Data", width: 170 },
					{ fieldname: "fixTime", label: "Time", fieldtype: "Datetime", width: 165 },
					{ fieldname: "latitude", label: "Latitude", fieldtype: "Float", width: 110 },
					{ fieldname: "longitude", label: "Longitude", fieldtype: "Float", width: 110 },
					{ fieldname: "speed", label: "Speed", fieldtype: "Data", width: 100 },
					{ fieldname: "course", label: "Course", fieldtype: "Float", width: 90 },
					{ fieldname: "altitude", label: "Altitude (m)", fieldtype: "Float", width: 110 },
					{ fieldname: "accuracy", label: "Accuracy (m)", fieldtype: "Float", width: 110 },
					{ fieldname: "address", label: "Address", fieldtype: "Data", width: 260 },
					{ fieldname: "map", label: "Map", fieldtype: "Data", width: 110 },
				],
				{
					speed: (value) => erp_tracking.format.speed(value),
					map: (value, row) =>
						`<a class="erpt-view-map" data-lat="${row.latitude}" data-lng="${row.longitude}">${__("View on Map")}</a>`,
				}
			),
			data: rows,
			layout: "fluid",
		});

		$table.on("click", ".erpt-view-map", (event) => {
			const $link = $(event.currentTarget);
			const row = rows.find(
				(r) => String(r.latitude) === $link.attr("data-lat") && String(r.longitude) === $link.attr("data-lng")
			);
			if (row) erp_tracking.map.show_point(row);
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
		erp_tracking.download("erp_tracking.api.export_live_positions", { ...this.filters(), fmt });
	}
}
