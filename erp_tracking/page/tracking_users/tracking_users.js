// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

// User CRUD is Manager-only (Section 41: Users are real Traccar login
// accounts, treated as an administrative action, not a general fleet
// resource - see the permission note in api.py). The New User button and
// row-click-to-edit are hidden client-side for non-Managers; the server
// enforces this regardless via require_admin() in every write endpoint.

const IS_MANAGER = frappe.user_roles.some((r) => ["System Manager", "ERP Tracking Manager"].includes(r));

frappe.pages["tracking_users"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Users"),
		single_column: true,
	});

	if (IS_MANAGER) {
		page.set_primary_action(__("New User"), () => show_user_form_dialog(null, () => list.load({ refresh: true })), "fa fa-plus");
	}

	const $container = $(`<div></div>`).appendTo(page.body);

	const list = new erp_tracking.ListEngine({
		wrapper: $container,
		method: "erp_tracking.api.get_users",
		page_length: 20,
		columns: [
			{ label: __("Name"), field: "name" },
			{ label: __("Email"), field: "email" },
			{ label: __("Phone"), field: "phone", format: (v) => v || "—" },
			{
				label: __("Administrator"),
				field: "administrator",
				format: (v) => (v ? `<span class="indicator-pill blue">${__("Yes")}</span>` : "—"),
			},
			{
				label: __("Readonly"),
				field: "readonly",
				format: (v) => (v ? __("Yes") : __("No")),
			},
			{
				label: __("Disabled"),
				field: "disabled",
				format: (v) => (v ? `<span class="indicator-pill danger">${__("Yes")}</span>` : `<span class="indicator-pill success">${__("No")}</span>`),
			},
			{
				label: __("Expiration"),
				field: "expirationTime",
				format: (v) => (v ? frappe.datetime.prettyDate(v) : "—"),
			},
			{ label: __("Device Limit"), field: "deviceLimit", format: (v) => (v ?? "—") },
			{ label: __("User Limit"), field: "userLimit", format: (v) => (v ?? "—") },
		],
		on_row_click: IS_MANAGER ? (row) => show_user_form_dialog(row, () => list.load({ refresh: true })) : null,
	});
	list.load();
};

function show_user_form_dialog(user, on_done) {
	const is_new = !user;

	const dialog = new frappe.ui.Dialog({
		title: is_new ? __("New User") : __("Edit User"),
		fields: [
			{ fieldtype: "Data", fieldname: "name", label: __("Name"), reqd: 1 },
			{ fieldtype: "Data", fieldname: "email", label: __("Email"), reqd: 1, options: "Email" },
			{ fieldtype: "Column Break" },
			{ fieldtype: "Data", fieldname: "phone", label: __("Phone") },
			{ fieldtype: "Int", fieldname: "device_limit", label: __("Device Limit") },
			{ fieldtype: "Section Break" },
			{
				fieldtype: "Password",
				fieldname: "password",
				label: is_new ? __("Password") : __("New Password (leave blank to keep current)"),
				reqd: is_new,
				// Deliberately never pre-filled on edit (Section 41): this
				// field is write-only. An empty value on update means
				// "don't change the password", not "clear it" - handled
				// server-side in users.py's update_user().
			},
			{ fieldtype: "Column Break" },
			{ fieldtype: "Check", fieldname: "administrator", label: __("Administrator") },
			{ fieldtype: "Check", fieldname: "disabled", label: __("Disabled") },
		],
		primary_action_label: is_new ? __("Create") : __("Save"),
		primary_action: (values) => {
			dialog.disable_primary_action();
			const method = is_new ? "erp_tracking.api.create_user" : "erp_tracking.api.update_user";
			const args = is_new
				? {
						name: values.name,
						email: values.email,
						password: values.password,
						administrator: values.administrator,
						disabled: values.disabled,
						phone: values.phone,
						device_limit: values.device_limit,
				  }
				: {
						user_id: user.id,
						name: values.name,
						email: values.email,
						password: values.password || undefined,
						administrator: values.administrator,
						disabled: values.disabled,
						phone: values.phone,
						deviceLimit: values.device_limit,
				  };

			frappe.call({
				method,
				args,
				callback: (r) => {
					const result = r.message || {};
					if (result.success) {
						frappe.show_alert({ message: is_new ? __("User created.") : __("User updated."), indicator: "green" });
						dialog.hide();
						on_done && on_done();
					} else {
						frappe.msgprint(result.message || __("Unable to save user."));
					}
					dialog.enable_primary_action();
				},
				error: () => dialog.enable_primary_action(),
			});
		},
	});

	if (!is_new) {
		dialog.set_values({
			name: user.name,
			email: user.email,
			phone: user.phone,
			device_limit: user.deviceLimit,
			administrator: user.administrator,
			disabled: user.disabled,
			// password intentionally omitted - see field description above
		});

		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete user {0}? This cannot be undone.", [user.name]), () => {
				frappe.call({
					method: "erp_tracking.api.delete_user",
					args: { user_id: user.id },
					callback: (r) => {
						const result = r.message || {};
						if (result.success) {
							frappe.show_alert({ message: __("User deleted."), indicator: "green" });
							dialog.hide();
							on_done && on_done();
						} else {
							frappe.msgprint(result.message || __("Unable to delete user."));
						}
					},
				});
			});
		});
	}

	dialog.show();
}
