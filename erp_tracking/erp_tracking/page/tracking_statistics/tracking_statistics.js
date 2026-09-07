// Server statistics with a chart per metric returned by /statistics.
frappe.pages["tracking-statistics"].on_page_load = async function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Server Statistics"),
		single_column: true,
	});

	const $container = $(`
		<div class="erpt-page">
			<div class="erpt-kpi"></div>
			<div class="erpt-chart"></div>
			<div class="erpt-body"></div>
		</div>`).appendTo(page.main);

	const $kpi = $container.find(".erpt-kpi");
	const $chart = $container.find(".erpt-chart");
	const $body = $container.find(".erpt-body");
	if (await erp_tracking.guard($body)) return;

	const from_field = page.add_field({ fieldname: "from", label: __("From"), fieldtype: "Date" });
	const to_field = page.add_field({ fieldname: "to", label: __("To"), fieldtype: "Date" });
	from_field.set_input(frappe.datetime.add_days(frappe.datetime.get_today(), -30));
	to_field.set_input(frappe.datetime.get_today());

	page.set_primary_action(__("Generate"), () => load());
	await load();

	async function load() {
		$body.html(`<div class="erpt-loading text-muted">${__("Loading...")}</div>`);
		const response = await erp_tracking.call("erp_tracking.api.get_statistics", {
			from_time: from_field.get_value(),
			to_time: to_field.get_value(),
		});

		if (!response.success) {
			$kpi.empty();
			$chart.empty();
			$body.html(erp_tracking.empty_state({ title: response.message }));
			return;
		}

		const data = response.data;
		erp_tracking.render_cards($kpi, [
			{ label: __("Requests"), value: data.totals.requests },
			{ label: __("Messages Received"), value: data.totals.messagesReceived },
			{ label: __("Messages Stored"), value: data.totals.messagesStored },
			{ label: __("Peak Active Devices"), value: Math.max(0, ...(data.items || []).map((r) => r.activeDevices || 0)) },
		]);

		if (!(data.items || []).length) {
			$chart.empty();
			$body.html(erp_tracking.empty_state({ title: __("No statistics for this period") }));
			return;
		}

		$chart.empty();
		new frappe.Chart($chart.get(0), {
			title: __("Server activity"),
			data: {
				labels: (data.labels || []).map((label) => erp_tracking.format.datetime(label)),
				datasets: data.datasets,
			},
			type: "line",
			height: 280,
			colors: ["#2490EF", "#28A745", "#F5A623", "#E74C3C", "#6C7680"],
			axisOptions: { xIsSeries: true },
		});

		$body.empty();
		const $table = $('<div class="erpt-datatable"></div>').appendTo($body);
		new frappe.DataTable($table.get(0), {
			columns: erp_tracking.to_datatable_columns([
				{ fieldname: "captureTime", label: "Capture Time", fieldtype: "Datetime", width: 180 },
				{ fieldname: "activeUsers", label: "Active Users", fieldtype: "Int", width: 130 },
				{ fieldname: "activeDevices", label: "Active Devices", fieldtype: "Int", width: 140 },
				{ fieldname: "requests", label: "Requests", fieldtype: "Int", width: 120 },
				{ fieldname: "messagesReceived", label: "Messages Received", fieldtype: "Int", width: 170 },
				{ fieldname: "messagesStored", label: "Messages Stored", fieldtype: "Int", width: 160 },
			]),
			data: data.items,
			layout: "fluid",
		});
	}
};
