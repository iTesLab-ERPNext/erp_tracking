// Audit log - restricted to ERP Tracking Manager and System Manager.
frappe.pages["tracking-audit"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Audit Logs"),
		single_column: true,
	});

	const $container = $(`
		<div class="erpt-page">
			<div class="erpt-body"></div>
			<div class="erpt-footer"></div>
		</div>`).appendTo(page.main);

	const $body = $container.find(".erpt-body");
	const $footer = $container.find(".erpt-footer");
	if (await erp_tracking.guard($body)) return;

	const config = await erp_tracking.get_config();
	const page_length = config.page_length || 20;
	let offset = 0;

	const from_field = page.add_field({ fieldname: "from", label: __("From"), fieldtype: "Date" });
	const to_field = page.add_field({ fieldname: "to", label: __("To"), fieldtype: "Date" });
	from_field.set_input(frappe.datetime.add_days(frappe.datetime.get_today(), -7));
	to_field.set_input(frappe.datetime.get_today());

	page.set_primary_action(__("Show Log"), () => {
		offset = 0;
		load();
	});
	erp_tracking.add_export_menu(page, (fmt) =>
		erp_tracking.download("erp_tracking.api.export_audit_log", {
			from_time: from_field.get_value(),
			to_time: to_field.get_value(),
			fmt,
		})
	);

	await load();

	async function load() {
		$body.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);
		const response = await erp_tracking.call("erp_tracking.api.get_audit_log", {
			from_time: from_field.get_value(),
			to_time: to_field.get_value(),
			limit: page_length,
			offset,
		});

		if (!response.success) {
			$body.html(erp_tracking.empty_state({ title: response.message }));
			$footer.empty();
			return;
		}

		const data = response.data;
		const rows = data.items || [];
		if (!rows.length) {
			$body.html(erp_tracking.empty_state({ title: __("No audit entries in this period") }));
			$footer.empty();
			return;
		}

		$body.empty();
		const $table = $('<div class="erpt-datatable"></div>').appendTo($body);
		new frappe.DataTable($table.get(0), {
			columns: erp_tracking.to_datatable_columns([
				{ fieldname: "actionTime", label: "Date", fieldtype: "Datetime", width: 170 },
				{ fieldname: "userEmail", label: "User", fieldtype: "Data", width: 220 },
				{ fieldname: "actionType", label: "Action", fieldtype: "Data", width: 140 },
				{ fieldname: "objectType", label: "Object", fieldtype: "Data", width: 160 },
				{ fieldname: "objectId", label: "Object ID", fieldtype: "Int", width: 110 },
				{ fieldname: "attributes", label: "Details", fieldtype: "Data", width: 280 },
			]),
			data: rows,
			layout: "fluid",
		});

		erp_tracking.pagination(
			$footer,
			{
				offset: data.offset,
				page_length: data.limit || page_length,
				count: rows.length,
				total: data.total,
				has_more: data.offset + rows.length < data.total,
			},
			(new_offset) => {
				offset = new_offset;
				load();
			}
		);
	}
};
