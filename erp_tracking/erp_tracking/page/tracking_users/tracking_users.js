// Traccar Users. This page is already Manager-only (see the Page's own
// `roles`), so create/edit/delete are unconditional here - the server
// still enforces ensure_admin() on every write regardless. The password
// field is write-only end to end: never pre-filled on edit, and left out
// of the outgoing payload entirely when blank so an existing password is
// never overwritten by accident (see users.update_user).
frappe.pages["tracking-users"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Traccar Users"),
		single_column: true,
	});

	await erp_tracking.get_config();

	const engine = new erp_tracking.ListEngine({
		page,
		parent: page.main,
		resource: "users",
		filters: [],
		column_overrides: {},
		primary_action: { label: __("New User"), action: () => open_user_dialog(engine) },
		on_row_click: (row) => open_user_dialog(engine, row),
	});

	await engine.setup();
	wrapper.erp_tracking_engine = engine;
};

function open_user_dialog(engine, user) {
	const editing = Boolean(user && user.id);
	const dialog = new frappe.ui.Dialog({
		title: editing ? __("Edit User") : __("New User"),
		fields: [
			{ fieldname: "name", label: __("Name"), fieldtype: "Data", reqd: 1, default: user?.name },
			{
				fieldname: "email",
				label: __("Email"),
				fieldtype: "Data",
				options: "Email",
				reqd: 1,
				default: user?.email,
			},
			{ fieldname: "column_break_1", fieldtype: "Column Break" },
			{ fieldname: "phone", label: __("Phone"), fieldtype: "Data", default: user?.phone },
			{ fieldname: "deviceLimit", label: __("Device Limit"), fieldtype: "Int", default: user?.deviceLimit },
			{ fieldname: "section_break_1", fieldtype: "Section Break" },
			{
				fieldname: "password",
				label: editing ? __("New Password (leave blank to keep current)") : __("Password"),
				fieldtype: "Password",
				reqd: !editing,
			},
			{ fieldname: "column_break_2", fieldtype: "Column Break" },
			{
				fieldname: "administrator",
				label: __("Administrator"),
				fieldtype: "Check",
				default: user?.administrator ? 1 : 0,
			},
			{ fieldname: "disabled", label: __("Disabled"), fieldtype: "Check", default: user?.disabled ? 1 : 0 },
		],
		primary_action_label: __("Save"),
		async primary_action(values) {
			const payload = { ...values };
			if (!payload.password) delete payload.password;

			const response = await erp_tracking.call("erp_tracking.api.save_user", {
				payload: JSON.stringify(payload),
				user_id: editing ? user.id : null,
			});
			if (response.success) {
				dialog.hide();
				frappe.show_alert({ message: __("User saved"), indicator: "green" });
				engine.refresh(true);
			}
		},
	});

	if (editing) {
		dialog.set_secondary_action_label(__("Delete"));
		dialog.set_secondary_action(() => {
			frappe.confirm(__("Delete user {0}? This cannot be undone.", [user.name]), async () => {
				const response = await erp_tracking.call("erp_tracking.api.delete_user", { user_id: user.id });
				if (response.success) {
					dialog.hide();
					frappe.show_alert({ message: __("User deleted"), indicator: "green" });
					engine.refresh(true);
				}
			});
		});
	}

	dialog.show();
}
