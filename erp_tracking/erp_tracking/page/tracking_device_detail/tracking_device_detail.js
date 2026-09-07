// Device details: overview plus tabs backed by the documented endpoints.
frappe.pages["tracking-device-detail"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Device Details"),
		single_column: true,
	});
	wrapper.erp_tracking_detail = new DeviceDetail(page, wrapper);
};

frappe.pages["tracking-device-detail"].on_page_show = function (wrapper) {
	const device_id = frappe.get_route()[1];
	wrapper.erp_tracking_detail.load(device_id);
};

const TABS = [
	{ key: "overview", label: "Overview" },
	{ key: "positions", label: "Positions" },
	{ key: "trips", label: "Trips" },
	{ key: "stops", label: "Stops" },
	{ key: "events", label: "Events" },
	{ key: "maintenance", label: "Maintenance" },
	{ key: "commands", label: "Commands" },
	{ key: "geofences", label: "Geofences" },
];

class DeviceDetail {
	constructor(page) {
		this.page = page;
		this.$container = $(`
			<div class="erpt-page">
				<div class="erpt-header"></div>
				<ul class="nav nav-tabs erpt-tabs" style="margin-bottom:15px"></ul>
				<div class="erpt-tab-body"></div>
			</div>`).appendTo(page.main);

		this.$header = this.$container.find(".erpt-header");
		this.$tabs = this.$container.find(".erpt-tabs");
		this.$body = this.$container.find(".erpt-tab-body");
		this.active = "overview";
		this.render_tabs();
	}

	render_tabs() {
		this.$tabs.html(
			TABS.map(
				(tab) =>
					`<li class="nav-item"><a class="nav-link" href="#" data-tab="${tab.key}">${__(tab.label)}</a></li>`
			).join("")
		);
		this.$tabs.find("[data-tab]").on("click", (event) => {
			event.preventDefault();
			this.active = $(event.currentTarget).attr("data-tab");
			this.render_active();
		});
	}

	async load(device_id) {
		if (!device_id) {
			this.$body.html(erp_tracking.empty_state({ title: __("No device selected") }));
			return;
		}
		this.device_id = device_id;
		if (await erp_tracking.guard(this.$body)) return;

		const response = await erp_tracking.call("erp_tracking.api.get_device_overview", { device_id });
		if (!response.success) {
			this.$header.empty();
			this.$body.html(erp_tracking.empty_state({ title: response.message }));
			return;
		}

		this.device = response.data.device || {};
		this.position = response.data.position || null;
		this.page.set_title(this.device.name || __("Device Details"));
		this.render_header();
		this.render_active();
	}

	render_header() {
		const device = this.device;
		const position = this.position || {};
		const rows = [
			[__("Name"), device.name],
			[__("Unique ID"), device.uniqueId],
			[__("Status"), erp_tracking.format.status_badge(device.status)],
			[__("Last Update"), erp_tracking.format.datetime(device.lastUpdate)],
			[__("Category"), device.category],
			[__("Model"), device.model],
			[__("Phone"), device.phone],
			[__("Speed"), erp_tracking.format.speed(position.speed)],
			[__("Latitude"), position.latitude],
			[__("Longitude"), position.longitude],
			[__("Course"), position.course],
			[__("Address"), position.address],
		];

		this.$header.html(`
			<div class="erpt-detail-grid">
				${rows
					.map(
						([label, value]) => `
					<div>
						<div class="erpt-detail-label">${label}</div>
						<div class="erpt-detail-value">${value === undefined || value === null || value === "" ? "&mdash;" : value}</div>
					</div>`
					)
					.join("")}
			</div>`);
	}

	render_active() {
		this.$tabs.find(".nav-link").removeClass("active");
		this.$tabs.find(`[data-tab="${this.active}"]`).addClass("active");
		this.$body.empty();

		const handlers = {
			overview: () => this.render_overview(),
			positions: () => this.open_route("tracking-position-history"),
			trips: () => this.open_report("trips"),
			stops: () => this.open_report("stops"),
			events: () => this.open_route("tracking-events"),
			maintenance: () => this.render_list("maintenance"),
			commands: () => this.render_commands(),
			geofences: () => this.render_list("geofences"),
		};
		(handlers[this.active] || handlers.overview)();
	}

	render_overview() {
		const $map = $('<div style="height:420px"></div>').appendTo(this.$body);
		if (this.position && this.position.latitude !== undefined) {
			erp_tracking.map.render($map.get(0), { points: [this.position] });
		} else {
			$map.html(
				erp_tracking.empty_state({
					title: __("No position reported yet"),
					message: __("The device has not sent a location to Traccar."),
				})
			);
		}
	}

	open_route(route) {
		this.$body.html(
			`<button class="btn btn-primary btn-sm" data-open>${__("Open")}</button>`
		);
		this.$body.find("[data-open]").on("click", () => frappe.set_route(route, this.device_id));
	}

	open_report(report) {
		this.$body.html(`<button class="btn btn-primary btn-sm" data-open>${__("Open")}</button>`);
		this.$body.find("[data-open]").on("click", () => frappe.set_route("tracking-reports", report));
	}

	async render_list(resource) {
		const response = await erp_tracking.call("erp_tracking.api.get_list", {
			resource,
			filters: JSON.stringify({ deviceId: this.device_id, limit: 100 }),
		});
		if (!response.success) {
			this.$body.html(erp_tracking.empty_state({ title: response.message }));
			return;
		}
		const data = response.data;
		if (!(data.items || []).length) {
			this.$body.html(erp_tracking.empty_state({ title: __("No records found") }));
			return;
		}
		const $table = $('<div class="erpt-datatable"></div>').appendTo(this.$body);
		new frappe.DataTable($table.get(0), {
			columns: erp_tracking.to_datatable_columns(data.columns),
			data: data.items,
			layout: "fluid",
		});
	}

	async render_commands() {
		const response = await erp_tracking.call("erp_tracking.api.get_device_saved_commands", {
			device_id: this.device_id,
		});
		if (!response.success) {
			this.$body.html(erp_tracking.empty_state({ title: response.message }));
			return;
		}
		const rows = response.data || [];
		this.$body.html(
			`<button class="btn btn-primary btn-sm" data-send style="margin-bottom:10px">${__("Send Command")}</button>`
		);
		this.$body.find("[data-send]").on("click", () =>
			erp_tracking.send_command_dialog({ device_id: this.device_id })
		);

		if (!rows.length) {
			$(erp_tracking.empty_state({ title: __("No saved commands for this device") })).appendTo(this.$body);
			return;
		}
		const $table = $('<div class="erpt-datatable"></div>').appendTo(this.$body);
		new frappe.DataTable($table.get(0), {
			columns: [
				{ id: "id", name: __("ID"), width: 70 },
				{ id: "description", name: __("Description"), width: 260 },
				{ id: "type", name: __("Type"), width: 180 },
			],
			data: rows,
			layout: "fluid",
		});
	}
}
