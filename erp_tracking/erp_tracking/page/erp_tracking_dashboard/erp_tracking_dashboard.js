// ERP Tracking dashboard: fleet counters, connection state and quick actions.
frappe.pages["erp-tracking-dashboard"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("ERP Tracking Dashboard"),
		single_column: true,
	});

	const dashboard = new TrackingDashboard(page);
	await dashboard.setup();
	wrapper.erp_tracking_dashboard = dashboard;
};

class TrackingDashboard {
	constructor(page) {
		this.page = page;
		this.$container = $(`
			<div class="erpt-page">
				<div class="erpt-connection"></div>
				<div class="erpt-cards-wrapper"></div>
				<div class="erpt-actions"></div>
			</div>`).appendTo(page.main);
	}

	async setup() {
		this.page.set_secondary_action(__("Refresh"), () => this.refresh(true));
		this.page.add_menu_item(__("Traccar Settings"), () => frappe.set_route("Form", "Traccar Settings"));
		this.render_quick_actions();
		await this.refresh();
	}

	async refresh(force = false) {
		const $cards = this.$container.find(".erpt-cards-wrapper");
		$cards.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);

		const config = await erp_tracking.get_config(true);
		if (!config.enabled || !config.configured) {
			this.render_connection(false, __("Traccar is not configured."));
			$cards.html(
				erp_tracking.empty_state({
					title: __("Traccar is not configured."),
					message: __("Add the server URL and credentials in Traccar Settings."),
					action: config.can_manage
						? `<button class="btn btn-primary btn-sm" data-action="settings">${__("Open Traccar Settings")}</button>`
						: "",
				})
			);
			$cards.find('[data-action="settings"]').on("click", () => frappe.set_route("Form", "Traccar Settings"));
			return;
		}

		const response = await erp_tracking.call("erp_tracking.api.get_dashboard", { refresh: force ? 1 : 0 }, { silent: true });

		if (!response.success) {
			this.render_connection(false, response.message);
			$cards.html(
				erp_tracking.empty_state({
					title: response.message || __("Traccar server unavailable."),
					message: __("The last request to Traccar failed. Check the server and the credentials."),
				})
			);
			return;
		}

		const data = response.data;
		this.render_connection(true, __("Last synchronised at {0}", [erp_tracking.format.datetime(data.synced_at)]), data.server_version);

		erp_tracking.render_cards($cards, [
			{ label: __("Total Devices"), value: data.cards.devices, route: "tracking-devices", tone: "primary" },
			{ label: __("Online Devices"), value: data.cards.online, route: "tracking-positions", tone: "success" },
			{ label: __("Offline Devices"), value: data.cards.offline, route: "tracking-devices", tone: "danger" },
			{ label: __("Groups"), value: data.cards.groups, route: "tracking-groups" },
			{ label: __("Users"), value: data.cards.users, route: "tracking-users" },
			{ label: __("Geofences"), value: data.cards.geofences, route: "tracking-geofences" },
			{ label: __("Events Today"), value: data.cards.events_today, route: "tracking-events", tone: "warning" },
			{ label: __("Trips Today"), value: data.cards.trips_today, route: "tracking-reports/trips" },
			{ label: __("Stops Today"), value: data.cards.stops_today, route: "tracking-reports/stops" },
		]);
	}

	render_connection(connected, message, version) {
		const indicator = connected ? "green" : "red";
		const label = connected ? __("Connected") : __("Disconnected");
		this.$container.find(".erpt-connection").html(`
			<div class="erpt-card ${connected ? "success" : "danger"}" style="margin-top:15px">
				<div><span class="indicator-pill ${indicator}">${label}</span>
				${version ? `<span class="text-muted"> &middot; ${__("Traccar")} ${frappe.utils.escape_html(version)}</span>` : ""}</div>
				<div class="erpt-card-label">${frappe.utils.escape_html(message || "")}</div>
			</div>`);
	}

	render_quick_actions() {
		const actions = [
			["tracking-devices", __("Devices")],
			["tracking-positions", __("Live Positions")],
			["tracking-reports/trips", __("Trips")],
			["tracking-reports/stops", __("Stops")],
			["tracking-events", __("Events")],
			["tracking-reports/summary", __("Reports")],
			["tracking-geofences", __("Geofences")],
			["tracking-commands", __("Commands")],
		];

		const html = actions
			.map(
				([route, label]) =>
					`<button class="btn btn-default btn-sm" data-route="${route}" style="margin:0 6px 6px 0">${label}</button>`
			)
			.join("");

		this.$container.find(".erpt-actions").html(`
			<div style="margin-top:5px">
				<div class="erpt-detail-label" style="margin-bottom:6px">${__("Quick actions")}</div>
				${html}
			</div>`);

		this.$container.find("[data-route]").on("click", function () {
			frappe.set_route($(this).attr("data-route"));
		});
	}
}
