"""Generic report engine driven by :data:`REPORT_CONFIG`.

One implementation covers summary, trips, stops, events, route and geofence
reports.  The report name is always validated against the allow-list, so no
caller can point the engine at an arbitrary Traccar path.
"""

from frappe import _
from frappe.utils import cint, cstr

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import NATIVE_REPORT_FORMATS, REPORT_CONFIG
from erp_tracking.integrations.traccar.devices import device_map
from erp_tracking.integrations.traccar.exceptions import TraccarAPIError
from erp_tracking.integrations.traccar.utils import (
	paginate,
	parse_id_list,
	parse_str_list,
	require,
	sort_rows,
	standard_response,
	stringify_attributes,
	to_iso,
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def get_report_config(name):
	config = REPORT_CONFIG.get(cstr(name))
	if not config:
		raise TraccarAPIError(_("Unknown report."), 400, detail=cstr(name))
	return config


def build_report_params(name, filters, include_download_only=False):
	"""Translate desk filters into the exact query parameters of the endpoint."""
	config = get_report_config(name)
	filters = filters or {}
	allowed = list(config["filters"])
	if include_download_only:
		allowed += config.get("download_only_filters", [])

	params = {}

	if "deviceId" in allowed:
		params["deviceId"] = parse_id_list(filters.get("deviceId"))
	if "groupId" in allowed:
		params["groupId"] = parse_id_list(filters.get("groupId"))
	if "geofenceId" in allowed:
		params["geofenceId"] = parse_id_list(filters.get("geofenceId"))
	if "type" in allowed:
		types = parse_str_list(filters.get("type")) or ["%"]
		# `type` is style=form, explode=false -> comma separated
		params["type"] = ",".join(types)
	if "alarm" in allowed and filters.get("alarm"):
		params["alarm"] = ",".join(parse_str_list(filters.get("alarm")))
	if "daily" in allowed and filters.get("daily"):
		params["daily"] = "true"

	params["from"] = to_iso(require(filters.get("from"), "From Date"))
	params["to"] = to_iso(require(filters.get("to"), "To Date"), end_of_day=True)

	if not params.get("deviceId") and not params.get("groupId") and "deviceId" in allowed:
		raise TraccarAPIError(_("Select at least one device or one group."), 400)

	return {k: v for k, v in params.items() if v not in (None, "", [])}


def fetch_report(name, filters):
	config = get_report_config(name)
	params = build_report_params(name, filters)
	rows = get_client().get(config["endpoint"], params) or []
	return list(rows)


def _decorate(name, rows):
	"""Resolve device names for reports whose rows only carry ``deviceId``."""
	if name in ("events", "route", "geofences"):
		devices = device_map()
		for row in rows:
			device = devices.get(cint(row.get("deviceId"))) or {}
			row["deviceName"] = device.get("name") or row.get("deviceId")
	return stringify_attributes(rows)


@standard_response
def run_report(name, filters=None, limit=None, offset=0, sort_by=None, sort_order="asc"):
	config = get_report_config(name)
	rows = _decorate(name, fetch_report(name, filters))
	rows = sort_rows(rows, sort_by, sort_order)

	result = paginate(rows, limit, offset)
	result["columns"] = config["columns"]
	result["label"] = config["label"]
	result["report"] = name
	result["kpi"] = build_kpis(name, rows)
	if name == "route":
		result["track"] = [
			[r.get("latitude"), r.get("longitude")]
			for r in rows
			if r.get("latitude") is not None and r.get("longitude") is not None
		]
	return result


def build_kpis(name, rows):
	"""Headline numbers for the report cards, computed from returned rows only."""
	if not rows:
		return []

	def total(field):
		return sum(float(r.get(field) or 0) for r in rows)

	def maximum(field):
		values = [float(r.get(field) or 0) for r in rows]
		return max(values) if values else 0

	if name == "summary":
		return [
			{"label": _("Devices"), "value": len(rows)},
			{"label": _("Total Distance (km)"), "value": round(total("distance") / 1000.0, 2)},
			{"label": _("Maximum Speed (km/h)"), "value": round(maximum("maxSpeed") * 1.852, 1)},
			{"label": _("Spent Fuel (l)"), "value": round(total("spentFuel"), 2)},
			{"label": _("Engine Hours"), "value": round(total("engineHours") / 3600000.0, 1)},
		]
	if name == "trips":
		return [
			{"label": _("Trips"), "value": len(rows)},
			{"label": _("Total Distance (km)"), "value": round(total("distance") / 1000.0, 2)},
			{"label": _("Driving Time (h)"), "value": round(total("duration") / 3600000.0, 1)},
			{"label": _("Maximum Speed (km/h)"), "value": round(maximum("maxSpeed") * 1.852, 1)},
		]
	if name == "stops":
		return [
			{"label": _("Stops"), "value": len(rows)},
			{"label": _("Stopped Time (h)"), "value": round(total("duration") / 3600000.0, 1)},
		]
	if name == "events":
		types = {}
		for row in rows:
			types[row.get("type")] = types.get(row.get("type"), 0) + 1
		top = sorted(types.items(), key=lambda kv: kv[1], reverse=True)[:3]
		return [{"label": _("Events"), "value": len(rows)}] + [
			{"label": _(cstr(k)), "value": v} for k, v in top
		]
	if name == "route":
		return [{"label": _("Positions"), "value": len(rows)}]
	if name == "geofences":
		return [{"label": _("Visits"), "value": len(rows)}]
	return []


def download_native(name, filters, fmt="xlsx"):
	"""Use Traccar's own ``/reports/{name}/{type}`` endpoint.

	``fmt='xlsx'`` returns ``(bytes, mime)``; ``fmt='mail'`` queues the report
	for e-mail delivery on the Traccar side and returns ``(None, None)``.
	"""
	config = get_report_config(name)
	if not config.get("download"):
		raise TraccarAPIError(
			_("Traccar does not provide a downloadable version of this report."), 400
		)
	fmt = cstr(fmt).lower()
	if fmt not in NATIVE_REPORT_FORMATS:
		raise TraccarAPIError(_("Unsupported report format."), 400)

	params = build_report_params(name, filters, include_download_only=True)
	endpoint = config["download"].format(type=fmt)
	accept = XLSX_MIME if fmt == "xlsx" else "*/*"
	content, _mime = get_client().request_raw("GET", endpoint, params=params, accept=accept)

	if fmt == "mail":
		return None, None
	return content, XLSX_MIME


@standard_response
def mail_report(name, filters=None):
	download_native(name, filters, fmt="mail")
	return {"queued": True}


def fetch_devices_report():
	"""``/reports/devices/{type}`` is download-only - no JSON variant exists."""
	from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS

	endpoint = TRACCAR_ENDPOINTS["devices_report_download"].format(type="xlsx")
	return get_client().request_raw("GET", endpoint, accept=XLSX_MIME)
