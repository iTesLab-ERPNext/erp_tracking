// Copyright (c) 2026, Your Company and contributors
// For license information, please see license.txt

frappe.pages["erp-tracking-users"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Users"),
		single_column: true,
	});

	const $container = $(`<div></div>`).appendTo(page.body);

	new erp_tracking.ListEngine({
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
	}).load();
};
