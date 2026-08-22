// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["tracking_server_info"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Server Information"),
		single_column: true,
	});

	const is_manager = frappe.user_roles.some((r) => ["System Manager", "ERP Tracking Manager"].includes(r));
	const $body = $(`<div></div>`).appendTo(page.body);

	function load() {
		$body.html(`<div class="text-muted text-center p-4">${__("Loading...")}</div>`);
		frappe.call({
			method: "erp_tracking.api.get_server_info",
			callback: (r) => {
				const result = r.message || {};
				if (!result.success) {
					const is_config = result.error === "TraccarConfigurationError";
					$body.html(`
						<div class="text-center text-muted p-4">
							<div style="font-size:1.5em;">${is_config ? "⚪" : "🔴"}</div>
							<div>${frappe.utils.escape_html(is_config ? __("Traccar is not configured.") : (result.message || __("Unable to load server information.")))}</div>
						</div>
					`);
					return;
				}
				render(result.data);
			},
		});
	}

	function render(server) {
		if (is_manager) {
			page.clear_primary_action();
			page.set_primary_action(__("Edit"), () => show_edit_dialog(server, load), "fa fa-edit");
		}

		// Only the fields the Server schema actually defines (Section 50: no
		// invented fields) - "Other available server information" from
		// Section 30 is covered by the Attributes row at the end.
		const rows = [
			[__("Version"), server.version || "—"],
			[__("Map"), server.map || "—"],
			[__("Map URL"), server.mapUrl || "—"],
			[__("Latitude"), server.latitude != null ? server.latitude.toFixed(5) : "—"],
			[__("Longitude"), server.longitude != null ? server.longitude.toFixed(5) : "—"],
			[__("Zoom"), server.zoom ?? "—"],
			[__("Coordinate Format"), server.coordinateFormat || "—"],
			[__("OpenID Enabled"), server.openIdEnabled ? `<span class="indicator-pill success">${__("Yes")}</span>` : `<span class="indicator-pill">${__("No")}</span>`],
			[__("OpenID Forced"), server.openIdForce ? __("Yes") : __("No")],
			[__("Registration Open"), server.registration ? __("Yes") : __("No")],
			[__("Read-only Server"), server.readonly ? __("Yes") : __("No")],
			[__("Device Read-only"), server.deviceReadonly ? __("Yes") : __("No")],
			[__("Limit Commands"), server.limitCommands ? __("Yes") : __("No")],
			[__("Force Settings"), server.forceSettings ? __("Yes") : __("No")],
			[__("Announcement"), server.announcement || "—"],
			[
				__("Attributes"),
				server.attributes && Object.keys(server.attributes).length
					? `<code>${frappe.utils.escape_html(JSON.stringify(server.attributes))}</code>`
					: "—",
			],
		];

		$body.html(`
			<table class="table table-bordered">
				${rows.map(([label, value]) => `<tr><th style="width:220px;">${label}</th><td>${value}</td></tr>`).join("")}
			</table>
		`);
	}

	load();
};

function show_edit_dialog(server, on_done) {
	const dialog = new frappe.ui.Dialog({
		title: __("Edit Server Settings"),
		fields: [
			{ fieldtype: "Data", fieldname: "map", label: __("Map") },
			{ fieldtype: "Data", fieldname: "map_url", label: __("Map URL") },
			{ fieldtype: "Float", fieldname: "latitude", label: __("Default Latitude") },
			{ fieldtype: "Float", fieldname: "longitude", label: __("Default Longitude") },
			{ fieldtype: "Int", fieldname: "zoom", label: __("Default Zoom") },
			{ fieldtype: "Data", fieldname: "coordinate_format", label: __("Coordinate Format") },
			{ fieldtype: "Small Text", fieldname: "announcement", label: __("Announcement") },
			{ fieldtype: "Check", fieldname: "registration", label: __("Allow Registration") },
			{ fieldtype: "Check", fieldname: "readonly", label: __("Read-only Server") },
			{ fieldtype: "Check", fieldname: "device_readonly", label: __("Device Read-only") },
			{ fieldtype: "Check", fieldname: "limit_commands", label: __("Limit Commands") },
			{ fieldtype: "Check", fieldname: "force_settings", label: __("Force Server Settings") },
		],
		primary_action_label: __("Save"),
		primary_action: (values) => {
			dialog.disable_primary_action();
			frappe.call({
				method: "erp_tracking.api.update_server_info",
				args: {
					map: values.map,
					mapUrl: values.map_url,
					latitude: values.latitude,
					longitude: values.longitude,
					zoom: values.zoom,
					coordinateFormat: values.coordinate_format,
					announcement: values.announcement,
					registration: values.registration,
					readonly: values.readonly,
					deviceReadonly: values.device_readonly,
					limitCommands: values.limit_commands,
					forceSettings: values.force_settings,
				},
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: __("Server settings updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to update server settings."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	dialog.set_values({
		map: server.map,
		map_url: server.mapUrl,
		latitude: server.latitude,
		longitude: server.longitude,
		zoom: server.zoom,
		coordinate_format: server.coordinateFormat,
		announcement: server.announcement,
		registration: server.registration,
		readonly: server.readonly,
		device_readonly: server.deviceReadonly,
		limit_commands: server.limitCommands,
		force_settings: server.forceSettings,
	});

	dialog.show();
}
