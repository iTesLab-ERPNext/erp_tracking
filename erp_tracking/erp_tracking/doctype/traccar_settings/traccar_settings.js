// Traccar Settings form: connection test and status indicator.
frappe.ui.form.on("Traccar Settings", {
	refresh(frm) {
		frm.disable_save();
		frm.page.set_primary_action(__("Save"), () => frm.save());

		frm.add_custom_button(__("Test Connection"), () => test_connection(frm));
		frm.add_custom_button(__("Clear Cache"), () => {
			frappe.call({
				method: "erp_tracking.api.clear_tracking_cache",
				callback: () => frappe.show_alert({ message: __("Cache cleared"), indicator: "green" }),
			});
		});
		frm.add_custom_button(__("Open Dashboard"), () => frappe.set_route("erp-tracking-dashboard"));

		render_status(frm);
	},

	auth_type(frm) {
		frm.set_value("connection_status", "Not Tested");
	},
});

function render_status(frm) {
	const status = frm.doc.connection_status || "Not Tested";
	const map = {
		Connected: ["green", __("Connection successful")],
		Failed: ["red", frm.doc.last_error || __("Authentication failed")],
		"Not Tested": ["orange", __("Connection not tested yet")],
	};
	const [colour, message] = map[status] || map["Not Tested"];

	frm.dashboard.clear_headline();
	frm.dashboard.set_headline(
		`<span class="indicator ${colour}">${frappe.utils.escape_html(message)}</span>`
	);
}

function test_connection(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the settings before testing the connection."));
		return;
	}

	frappe.dom.freeze(__("Contacting the Traccar server..."));
	frappe.call({
		method: "erp_tracking.api.test_connection",
		always: () => frappe.dom.unfreeze(),
		callback(r) {
			const result = r.message || {};
			if (result.success) {
				frappe.msgprint({
					title: __("Connection successful"),
					indicator: "green",
					message: __("Signed in to Traccar {0} as {1}.", [
						frappe.utils.escape_html(result.server_version || "?"),
						frappe.utils.escape_html(result.account || "?"),
					]),
				});
			} else {
				frappe.msgprint({
					title: indicator_title(result.status_code),
					indicator: result.status_code === 408 ? "orange" : "red",
					message: frappe.utils.escape_html(result.message || __("Connection failed")),
				});
			}
			frm.reload_doc();
		},
	});
}

function indicator_title(status_code) {
	if (status_code === 401 || status_code === 403) return __("Authentication failed");
	if (status_code === 408) return __("Connection timeout");
	if (status_code === 0) return __("Invalid configuration");
	return __("Server unavailable");
}
