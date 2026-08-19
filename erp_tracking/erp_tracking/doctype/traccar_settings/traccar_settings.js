// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.ui.form.on("Traccar Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => {
			test_connection(frm);
		}).addClass("btn-primary");

		render_status_indicator(frm);
	},

	connection_status(frm) {
		render_status_indicator(frm);
	},
});

function test_connection(frm) {
	frappe.show_alert({ message: __("Testing connection..."), indicator: "blue" });

	frappe.call({
		method: "erp_tracking.erp_tracking.doctype.traccar_settings.traccar_settings.test_connection",
		freeze: true,
		freeze_message: __("Testing connection to Traccar..."),
		callback: (r) => {
			const result = r.message || {};
			frm.reload_doc();

			if (result.success) {
				frappe.show_alert({ message: __("🟢 {0}", [result.message]), indicator: "green" });
			} else {
				frappe.show_alert({ message: __("🔴 {0}", [result.message]), indicator: "red" });
			}
		},
	});
}

// Maps DocType status values to the emoji/color states described in the brief:
// 🟢 Connection successful / 🔴 Authentication failed / 🔴 Server unavailable
// 🟠 Connection timeout / 🔴 Invalid configuration
const STATUS_MAP = {
	"Connected": { emoji: "🟢", indicator: "green" },
	"Authentication Failed": { emoji: "🔴", indicator: "red" },
	"Server Unavailable": { emoji: "🔴", indicator: "red" },
	"Timeout": { emoji: "🟠", indicator: "orange" },
	"Invalid Configuration": { emoji: "🔴", indicator: "red" },
	"Not Tested": { emoji: "⚪", indicator: "grey" },
};

function render_status_indicator(frm) {
	const status = frm.doc.connection_status || "Not Tested";
	const meta = STATUS_MAP[status] || STATUS_MAP["Not Tested"];
	frm.dashboard.clear_headline();
	frm.dashboard.set_headline(`${meta.emoji} ${__(status)}`);
}
