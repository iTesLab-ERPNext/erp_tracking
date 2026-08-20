"""Generic report engine (Section 37) covering Trips, Stops, Summary, Events.

One module, one REPORT_CONFIG map, four reports - instead of a hardcoded
module per report type. Every report's request shape (device/group required,
from/to required, same param encoding) is identical per the spec, so
generate_report()/download_report() are shared; only the endpoint keys and
optional extra filters differ per entry in REPORT_CONFIG.

IMPORTANT deviation from a literal reading of Sections 16-18/21 ("Export
CSV, Export XLSX, Export PDF"): the OpenAPI spec's report download
endpoints (`/reports/{trips,stops,summary,events}/{type}`) only support
`type=xlsx` (native spreadsheet) and `type=mail` (server queues an email
delivery). There is no CSV or PDF export operation for these reports
anywhere in the spec. Per Section 50 ("do not invent endpoints... do not
assume CRUD/operations exist"), this module exposes Export XLSX and Email
Report only. CSV/GPX/KML export DOES exist for raw positions (see
positions.py, Section 15) - that is unrelated to these aggregate reports.

Also per the note in config.py: there is no `GET /events` list endpoint.
The Events page (Section 20) is built on `GET /reports/events` here -
functionally the same request as the Events Report (Section 21), just
rendered as a live list with badges instead of an export-oriented table.
"""

from __future__ import annotations

from .client import TraccarClient
from .exceptions import TraccarError
from .utils import to_iso8601

REPORT_CONFIG = {
	"trips": {
		"endpoint": "reports_trips",
		"download_endpoint": "reports_trips_type",
		"supports_event_types": False,
		"supports_daily": False,
	},
	"stops": {
		"endpoint": "reports_stops",
		"download_endpoint": "reports_stops_type",
		"supports_event_types": False,
		"supports_daily": False,
	},
	"summary": {
		"endpoint": "reports_summary",
		"download_endpoint": "reports_summary_type",
		"supports_event_types": False,
		"supports_daily": True,
	},
	"events": {
		"endpoint": "reports_events",
		"download_endpoint": "reports_events_type",
		"supports_event_types": True,
		"supports_daily": False,
	},
}


def _client_error(message: str) -> dict:
	return {
		"success": False,
		"data": None,
		"message": message,
		"status_code": 400,
		"error": "TraccarClientValidationError",
	}


def _build_params(cfg: dict, device_ids=None, group_ids=None, from_date=None, to_date=None, event_types=None, daily=None) -> dict:
	if not device_ids and not group_ids:
		raise TraccarError("At least one device or group is required.", 400)
	if not from_date or not to_date:
		raise TraccarError("Both From and To dates are required.", 400)

	params = {"from": to_iso8601(from_date), "to": to_iso8601(to_date)}
	if device_ids:
		params["deviceId"] = [int(d) for d in device_ids]
	if group_ids:
		params["groupId"] = [int(g) for g in group_ids]
	if cfg["supports_event_types"] and event_types:
		params["type"] = list(event_types)
	if cfg["supports_daily"] and daily is not None:
		params["daily"] = bool(daily)
	return params


def generate_report(
	report_key: str,
	device_ids: list[int] | None = None,
	group_ids: list[int] | None = None,
	from_date=None,
	to_date=None,
	event_types: list[str] | None = None,
	daily: bool | None = None,
) -> dict:
	"""Fetch JSON rows for a report (Section 37 dynamic API request step).

	report_key is checked against REPORT_CONFIG, a fixed dict defined in
	this file - never user-supplied - satisfying Section 41's "validate
	report names against an allowed list."
	"""
	cfg = REPORT_CONFIG.get(report_key)
	if not cfg:
		return _client_error(f"Unknown report: {report_key}")

	try:
		params = _build_params(cfg, device_ids, group_ids, from_date, to_date, event_types, daily)
	except TraccarError as exc:
		return _client_error(exc.message)

	return TraccarClient().request_safe("GET", cfg["endpoint"], params=params)


def download_report(
	report_key: str,
	download_type: str,
	device_ids: list[int] | None = None,
	group_ids: list[int] | None = None,
	from_date=None,
	to_date=None,
	event_types: list[str] | None = None,
	daily: bool | None = None,
):
	"""Download or email a report via Traccar's native export (Section 39).

	Returns raw XLSX bytes when download_type == "xlsx", or None when
	download_type == "mail" (Traccar responds 204 and queues delivery
	server-side). Raises TraccarError on validation/API failure - the
	caller (a whitelisted method) turns that into a clean frappe.throw.
	"""
	cfg = REPORT_CONFIG.get(report_key)
	if not cfg:
		raise TraccarError(f"Unknown report: {report_key}", 400)
	if download_type not in ("xlsx", "mail"):
		raise TraccarError("Unsupported export type. Only 'xlsx' and 'mail' are available.", 400)

	params = _build_params(cfg, device_ids, group_ids, from_date, to_date, event_types, daily)
	accept = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
		if download_type == "xlsx"
		else "application/json"
	)

	result = TraccarClient().request(
		"GET",
		cfg["download_endpoint"],
		path_params={"type": download_type},
		params=params,
		accept=accept,
	)
	return result["data"]
