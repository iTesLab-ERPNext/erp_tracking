// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("ERP Tracking Dashboard"),
		single_column: true,
	});

	page.add_menu_item(__("Traccar Settings"), () => frappe.set_route("Form", "Traccar Settings"));

	new ERPTrackingDashboard(page);
};

class ERPTrackingDashboard {
	constructor(page) {
		this.page = page;
		this.$body = $(`<div class="erp-tracking-dashboard"></div>`).appendTo(page.body);

		this.page.set_primary_action(__("Refresh"), () => this.load(), "fa fa-refresh");

		this._render_shell();
		this.load();
	}

	_render_shell() {
		this.$body.html(`
			<div class="erp-tracking-conn-banner mb-3"></div>

			<div class="row erp-tracking-cards" style="row-gap: 16px;"></div>

			<div class="mt-4">
				<div class="text-muted small mb-2">${__("Last synchronization")}: <span class="erp-tracking-last-sync">—</span></div>
			</div>

			<div class="mt-4">
				<h5>${__("Quick Actions")}</h5>
				<div class="erp-tracking-quick-actions d-flex flex-wrap" style="gap: 8px;"></div>
			</div>
		`);

		this._render_quick_actions();
	}

	_render_quick_actions() {
		const actions = [
			{ label: __("Devices"), route: "tracking_devices" },
			{ label: __("Groups"), route: "tracking_groups" },
			{ label: __("Users"), route: "tracking_users" },
			{ label: __("Live Positions"), route: "tracking_positions" },
			{ label: __("Position History"), route: "tracking_position_history" },
			{ label: __("Route"), route: "tracking_route" },
			{ label: __("Trips"), route: "tracking_reports" },
			{ label: __("Stops"), route: "tracking_reports" },
			{ label: __("Events"), route: "tracking_events" },
			{ label: __("Reports"), route: "tracking_reports" },
			{ label: __("Geofences"), route: "tracking_geofences" },
			{ label: __("Notifications"), route: "tracking_notifications" },
			{ label: __("Commands"), route: "tracking_commands" },
			{ label: __("Drivers"), route: "tracking_drivers" },
			{ label: __("Maintenance"), route: "tracking_maintenance" },
			{ label: __("Calendars"), route: "tracking_calendars" },
			{ label: __("Server Info"), route: "tracking_server_info" },
			{ label: __("Health"), route: "tracking_health" },
			{ label: __("Statistics"), route: "tracking_statistics" },
			{ label: __("Audit Logs"), route: "tracking_audit" },
			{ label: __("Orders"), route: "tracking_orders" },
			{ label: __("Live Camera"), route: "tracking_live_video" },
		];

		const $actions = this.$body.find(".erp-tracking-quick-actions");
		actions.forEach((a) => {
			$(`<button class="btn btn-default btn-sm">${a.label}</button>`)
				.on("click", () => frappe.set_route(a.route))
				.appendTo($actions);
		});
	}

	load() {
		this._load_connection_status();
		this._load_summary();
	}

	_load_connection_status() {
		frappe.call({
			method: "erp_tracking.api.get_connection_status",
			callback: (r) => {
				const status = r.message || {};
				const connected = status.connection_status === "Connected";
				const $banner = this.$body.find(".erp-tracking-conn-banner");

				if (!status.configured || !status.enabled) {
					$banner.html(this._banner("⚪", __("Traccar is not configured."), "secondary"));
				} else if (connected) {
					$banner.html(this._banner("🟢", __("Connected to Traccar"), "success"));
				} else {
					$banner.html(this._banner("🔴", __("Disconnected — {0}", [status.connection_status || ""]), "danger"));
				}

				this.$body
					.find(".erp-tracking-last-sync")
					.text(status.last_connection_test ? frappe.datetime.prettyDate(status.last_connection_test) : __("Never"));
			},
		});
	}

	_banner(emoji, text, cls) {
		return `<div class="alert alert-${cls === "secondary" ? "secondary" : cls} d-flex align-items-center" style="gap:8px;">
			<span style="font-size:1.2em;">${emoji}</span> <span>${frappe.utils.escape_html(text)}</span>
		</div>`;
	}

	_load_summary() {
		const $cards = this.$body.find(".erp-tracking-cards");
		$cards.html(`<div class="col-12 text-muted p-4">${__("Loading dashboard...")}</div>`);

		frappe.call({
			method: "erp_tracking.api.get_dashboard_summary",
			callback: (r) => {
				const result = r.message || {};
				if (!result.success) {
					const is_config = result.error === "TraccarConfigurationError";
					$cards.html(`
						<div class="col-12 text-center text-muted p-4">
							<div style="font-size:1.5em;">${is_config ? "⚪" : "🔴"}</div>
							<div>${frappe.utils.escape_html(is_config ? __("Traccar is not configured.") : (result.message || __("Unable to load dashboard data.")))}</div>
						</div>
					`);
					return;
				}
				this._render_cards(result.data);
			},
		});
	}

	_render_cards(data) {
		const cards = [
			{ label: __("Total Devices"), value: data.devices_total },
			{ label: __("Online Devices"), value: data.devices_online, cls: "text-success" },
			{ label: __("Offline Devices"), value: data.devices_offline, cls: "text-danger" },
			{ label: __("Groups"), value: data.groups_total },
			{ label: __("Users"), value: data.users_total },
			{ label: __("Geofences"), value: data.geofences_total },
			{ label: __("Events Today"), value: data.events_today, note: __("Available after Reports (Phase 4)") },
			{ label: __("Trips Today"), value: data.trips_today, note: __("Available after Reports (Phase 4)") },
			{ label: __("Stops Today"), value: data.stops_today, note: __("Available after Reports (Phase 4)") },
		];

		const $cards = this.$body.find(".erp-tracking-cards");
		$cards.empty();

		cards.forEach((c) => {
			const display = c.value === null || c.value === undefined ? "—" : c.value;
			$(`
				<div class="col-md-4 col-sm-6">
					<div class="card p-3">
						<div class="text-muted small">${c.label}</div>
						<div class="h3 mb-0 ${c.cls || ""}">${display}</div>
						${c.note ? `<div class="text-muted small mt-1">${c.note}</div>` : ""}
					</div>
				</div>
			`).appendTo($cards);
		});
	}
}
