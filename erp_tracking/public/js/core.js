/**
 * ERP Tracking - shared desk helpers.
 *
 * The frontend only ever talks to whitelisted Frappe methods. It never holds a
 * Traccar URL, credential or Authorization header.
 */
frappe.provide("erp_tracking");

Object.assign(erp_tracking, {
	config: null,

	/** Call a whitelisted method and unwrap the standard response envelope. */
	async call(method, args = {}, { freeze = false, freeze_message = null, silent = false } = {}) {
		try {
			const r = await frappe.call({
				method,
				args,
				freeze,
				freeze_message: freeze_message || __("Loading..."),
			});
			const response = r.message || {};
			if (response.success === false && !silent) {
				erp_tracking.show_error(response);
			}
			return response;
		} catch (error) {
			if (!silent) {
				frappe.show_alert({ message: __("Request failed"), indicator: "red" });
			}
			return { success: false, data: null, message: __("Request failed"), status_code: 0 };
		}
	},

	show_error(response) {
		const indicator = response.status_code === 408 ? "orange" : "red";
		frappe.show_alert({
			message: frappe.utils.escape_html(response.message || __("Request failed")),
			indicator,
		}, 7);
	},

	/** Load the (secret-free) configuration snapshot once per session. */
	async get_config(refresh = false) {
		if (erp_tracking.config && !refresh) return erp_tracking.config;
		const response = await erp_tracking.call("erp_tracking.api.get_configuration_state", {}, { silent: true });
		erp_tracking.config = response.data || {};
		return erp_tracking.config;
	},

	/**
	 * Render the "Traccar is not configured" state. Returns true when the page
	 * should stop rendering.
	 */
	async guard(container) {
		const config = await erp_tracking.get_config();
		if (config.enabled && config.configured) return false;

		$(container).html(
			erp_tracking.empty_state({
				title: __("Traccar is not configured."),
				message: __("Set the server URL and credentials in Traccar Settings, then run Test Connection."),
				action: config.can_manage
					? `<button class="btn btn-primary btn-sm" data-action="open-settings">${__("Open Traccar Settings")}</button>`
					: "",
			})
		);
		$(container)
			.find('[data-action="open-settings"]')
			.on("click", () => frappe.set_route("Form", "Traccar Settings"));
		return true;
	},

	empty_state({ title, message, action = "" }) {
		return `
			<div class="erpt-empty">
				<div class="erpt-empty-title">${frappe.utils.escape_html(title)}</div>
				<div class="erpt-empty-message">${frappe.utils.escape_html(message || "")}</div>
				<div class="erpt-empty-action">${action}</div>
			</div>`;
	},

	/* ---------------------------------------------------------------- */
	/* Formatting                                                       */
	/* ---------------------------------------------------------------- */
	format: {
		datetime(value) {
			if (!value) return "";
			const cleaned = String(value).replace("Z", "").replace("T", " ");
			return frappe.datetime.str_to_user(cleaned) || value;
		},

		/** Traccar reports speed in knots. */
		speed(knots) {
			if (knots === null || knots === undefined || knots === "") return "";
			return `${(Number(knots) * 1.852).toFixed(1)} km/h`;
		},

		distance(metres) {
			if (!metres) return "0 km";
			return `${(Number(metres) / 1000).toFixed(2)} km`;
		},

		/** Traccar durations and engine hours are milliseconds. */
		duration(ms) {
			if (!ms) return "";
			const total = Math.round(Number(ms) / 1000);
			const h = Math.floor(total / 3600);
			const m = Math.floor((total % 3600) / 60);
			return h ? `${h} h ${m} min` : `${m} min`;
		},

		status_badge(status) {
			const map = {
				online: ["green", __("Online")],
				offline: ["red", __("Offline")],
				unknown: ["gray", __("Unknown")],
			};
			const [colour, label] = map[status] || ["gray", status || __("Unknown")];
			return `<span class="indicator-pill ${colour}">${label}</span>`;
		},

		event_badge(type, colour) {
			return `<span class="indicator-pill ${colour || "blue"}">${frappe.utils.escape_html(
				__(type || "")
			)}</span>`;
		},

		check(value) {
			return value ? __("Yes") : __("No");
		},
	},

	/** Turn a backend column definition into a frappe-datatable column. */
	to_datatable_columns(columns, overrides = {}) {
		return (columns || []).map((column) => {
			const custom = overrides[column.fieldname];
			return {
				id: column.fieldname,
				name: __(column.label),
				width: column.width || 140,
				editable: false,
				focusable: false,
				dropdown: false,
				format: (value, row, col, data) => {
					if (custom) return custom(value, data);
					if (value === null || value === undefined) return "";
					if (column.fieldtype === "Datetime") return erp_tracking.format.datetime(value);
					if (column.fieldtype === "Check") return erp_tracking.format.check(value);
					if (column.fieldtype === "Duration") return erp_tracking.format.duration(value);
					if (column.fieldtype === "Status") return erp_tracking.format.status_badge(value);
					if (column.fieldtype === "Float") return frappe.format(value, { fieldtype: "Float" });
					return frappe.utils.escape_html(String(value));
				},
			};
		});
	},

	/** Server-side download that carries the current page filters. */
	download(method, args) {
		const payload = {};
		Object.keys(args || {}).forEach((key) => {
			const value = args[key];
			payload[key] = typeof value === "object" ? JSON.stringify(value) : value;
		});
		open_url_post(`/api/method/${method}`, payload);
	},

	/** Standard export dropdown shared by every list and report page. */
	add_export_menu(page, handler, formats = ["csv", "xlsx", "pdf"]) {
		const labels = { csv: __("Export CSV"), xlsx: __("Export XLSX"), pdf: __("Export PDF"), gpx: __("Export GPX"), kml: __("Export KML") };
		formats.forEach((fmt) => page.add_menu_item(labels[fmt] || fmt.toUpperCase(), () => handler(fmt)));
	},

	/** Pagination footer used by both engines. */
	pagination(container, { offset, page_length, count, has_more, total }, on_change) {
		const $el = $(container).empty();
		const page_no = Math.floor(offset / page_length) + 1;
		const shown = total
			? __("Page {0} · {1} of {2}", [page_no, count, total])
			: __("Page {0} · {1} rows", [page_no, count]);

		$el.append(`
			<div class="erpt-pagination">
				<button class="btn btn-default btn-xs" data-action="prev" ${offset <= 0 ? "disabled" : ""}>${__("Previous")}</button>
				<span class="erpt-page-info">${shown}</span>
				<button class="btn btn-default btn-xs" data-action="next" ${has_more ? "" : "disabled"}>${__("Next")}</button>
			</div>`);

		$el.find('[data-action="prev"]').on("click", () => on_change(Math.max(offset - page_length, 0)));
		$el.find('[data-action="next"]').on("click", () => on_change(offset + page_length));
	},

	/** KPI cards used by the dashboard and the report engine. */
	render_cards(container, cards) {
		const html = cards
			.map(
				(card) => `
			<div class="erpt-card ${card.tone || ""}" ${card.route ? `data-route="${card.route}"` : ""}>
				<div class="erpt-card-value">${card.value === null || card.value === undefined ? "&mdash;" : frappe.utils.escape_html(String(card.value))}</div>
				<div class="erpt-card-label">${frappe.utils.escape_html(card.label)}</div>
			</div>`
			)
			.join("");
		$(container).html(`<div class="erpt-cards">${html}</div>`);
		$(container)
			.find("[data-route]")
			.on("click", function () {
				frappe.set_route($(this).attr("data-route"));
			});
	},

	/** Device / group / geofence choices for filter fields. */
	async filter_options(include = ["devices", "groups"]) {
		const response = await erp_tracking.call("erp_tracking.api.get_filter_options", {
			include: include.join(","),
		});
		return response.data || {};
	},

	default_from() {
		return frappe.datetime.add_days(frappe.datetime.get_today(), -7);
	},

	default_to() {
		return frappe.datetime.get_today();
	},
});
