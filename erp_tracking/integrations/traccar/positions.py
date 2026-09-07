"""Positions - live snapshot, history and Traccar's native exports.

Specification notes:
* ``GET /positions`` with no parameters returns the last known position of every
  device the account can see.
* ``deviceId`` requires ``from`` and ``to``.
* There are **no** ``limit``/``offset`` parameters, so history paging happens
  server-side after the window is fetched.
* ``/positions/csv``, ``/positions/gpx`` and ``/positions/kml`` are native
  exports and are used instead of re-encoding the data ourselves.
"""

from frappe import _
from frappe.utils import cint, cstr

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.devices import device_map
from erp_tracking.integrations.traccar.utils import (
	paginate,
	parse_id_list,
	require,
	sort_rows,
	standard_response,
	stringify_attributes,
	to_iso,
)

NATIVE_POSITION_FORMATS = {
	"csv": (TRACCAR_ENDPOINTS["positions_csv"], "text/csv", "csv"),
	"gpx": (TRACCAR_ENDPOINTS["positions_gpx"], "application/gpx+xml", "gpx"),
	"kml": (TRACCAR_ENDPOINTS["positions_kml"], "application/vnd.google-earth.kml+xml", "kml"),
}


def _decorate(rows, devices=None):
	"""Attach device name / status / group so the desk table can show them."""
	devices = devices if devices is not None else device_map()
	for row in rows or []:
		device = devices.get(cint(row.get("deviceId"))) or {}
		row["deviceName"] = device.get("name") or device.get("uniqueId") or row.get("deviceId")
		row["deviceStatus"] = device.get("status")
		row["groupId"] = device.get("groupId")
	return stringify_attributes(rows, keys=("attributes", "network", "geofenceIds"))


def fetch_latest(device_ids=None, group_id=None, status=None):
	rows = get_client().get(TRACCAR_ENDPOINTS["positions"]) or []
	devices = device_map()
	rows = _decorate(rows, devices)

	device_ids = parse_id_list(device_ids)
	if device_ids:
		rows = [r for r in rows if cint(r.get("deviceId")) in device_ids]
	if group_id:
		rows = [r for r in rows if cint(r.get("groupId")) == cint(group_id)]
	if status:
		rows = [r for r in rows if cstr(r.get("deviceStatus")) == cstr(status)]
	return rows


@standard_response
def get_latest_positions(device_ids=None, group_id=None, status=None, limit=None, offset=0, sort_by=None, sort_order="asc"):
	"""Live positions page - one snapshot per device."""
	rows = fetch_latest(device_ids=device_ids, group_id=group_id, status=status)
	rows = sort_rows(rows, sort_by or "deviceName", sort_order)
	return paginate(rows, limit, offset)


def fetch_history(device_id, from_time, to_time):
	device_id = cint(require(device_id, "Device"))
	params = {
		"deviceId": device_id,
		"from": to_iso(require(from_time, "From Date")),
		"to": to_iso(require(to_time, "To Date"), end_of_day=True),
	}
	rows = get_client().get(TRACCAR_ENDPOINTS["positions"], params) or []
	return _decorate(rows)


@standard_response
def get_position_history(device_id, from_time, to_time, limit=None, offset=0, sort_by=None, sort_order="asc"):
	rows = fetch_history(device_id, from_time, to_time)
	rows = sort_rows(rows, sort_by or "fixTime", sort_order)
	result = paginate(rows, limit, offset)
	# The map needs the whole track, not just the current page.
	result["track"] = [
		[r.get("latitude"), r.get("longitude")]
		for r in rows
		if r.get("latitude") is not None and r.get("longitude") is not None
	]
	return result


@standard_response
def get_positions_by_id(position_ids):
	ids = parse_id_list(position_ids)
	if not ids:
		return []
	return _decorate(get_client().get(TRACCAR_ENDPOINTS["positions"], {"id": ids}) or [])


def download_positions(device_id, from_time, to_time, fmt="csv", geofence_id=None):
	"""Use Traccar's native CSV/GPX/KML exports. Returns ``(bytes, mime, ext)``."""
	fmt = cstr(fmt).lower()
	if fmt not in NATIVE_POSITION_FORMATS:
		from erp_tracking.integrations.traccar.exceptions import TraccarAPIError

		raise TraccarAPIError(_("Unsupported position export format."), 400)

	endpoint, mime, extension = NATIVE_POSITION_FORMATS[fmt]
	params = {
		"deviceId": cint(require(device_id, "Device")),
		"from": to_iso(require(from_time, "From Date")),
		"to": to_iso(require(to_time, "To Date"), end_of_day=True),
	}
	# geofenceId is only documented on /positions/csv
	if geofence_id and fmt == "csv":
		params["geofenceId"] = cint(geofence_id)

	content, _content_type = get_client().request_raw("GET", endpoint, params=params, accept=mime)
	return content, mime, extension
