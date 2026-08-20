"""Positions feature module (Sections 14-15).

Live positions and position history both read from GET /positions - the
spec is explicit that deviceId requires from/to when used, and that id can
be used without from/to. This module mirrors that exactly rather than
inventing a simplified interface.

Native export endpoints (Section 15: "If the API provides native CSV/GPX
endpoints, use those endpoints instead of rebuilding the format
unnecessarily") are wired here too: /positions/csv, /positions/kml,
/positions/gpx. These return binary/text bodies, not JSON, so they go
through TraccarClient.request() directly with accept set appropriately
rather than through the JSON-shaped request_safe() helper.
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .exceptions import TraccarError
from .utils import to_iso8601

# Live positions change constantly - cache is only long enough to absorb a
# burst of repeated calls (e.g. a dashboard tile and the list page loading
# together), matching the policy already used in devices.py.
LIVE_CACHE_TTL_SECONDS = 10


def get_live_positions(device_id: int | None = None, refresh: bool = False) -> dict:
	"""Last known position for all (or one) of the user's devices.

	Matches GET /positions with no from/to - per the spec this returns the
	last known positions. deviceId alone (without from/to) is intentionally
	NOT passed through to Traccar here, since the spec requires from/to
	whenever deviceId is used; a bare single-device "live" position is
	obtained by filtering the all-devices response instead, which needs no
	extra round trip and matches what the demo servers actually return.
	"""
	cache_key = f"erp_tracking:positions:live"

	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			result = cached
		else:
			result = None
	else:
		result = None

	if result is None:
		result = TraccarClient().request_safe("GET", "positions")
		if result["success"]:
			frappe.cache().set_value(cache_key, result, expires_in_sec=LIVE_CACHE_TTL_SECONDS)

	if not result["success"] or device_id is None:
		return result

	filtered = [p for p in (result["data"] or []) if p.get("deviceId") == int(device_id)]
	return {**result, "data": filtered}


def get_position_history(device_id: int, from_date, to_date) -> dict:
	"""Position history for one device over a time range.

	Matches GET /positions?deviceId=&from=&to= (Section 15). deviceId is
	required together with from/to per the spec.
	"""
	if not device_id:
		return _client_error("A device is required to fetch position history.")
	if not from_date or not to_date:
		return _client_error("Both From and To dates are required.")

	params = {
		"deviceId": int(device_id),
		"from": to_iso8601(from_date),
		"to": to_iso8601(to_date),
	}
	return TraccarClient().request_safe("GET", "positions", params=params)


def delete_position_range(device_id: int, from_date, to_date) -> dict:
	"""Delete all positions for a device in a time span - matches DELETE
	/positions. Manager-only; wired here for completeness of the endpoint
	but not exposed in the UI in this phase.
	"""
	params = {
		"deviceId": int(device_id),
		"from": to_iso8601(from_date),
		"to": to_iso8601(to_date),
	}
	return TraccarClient().request_safe("DELETE", "positions", params=params)


def _export(endpoint_key: str, device_id: int, from_date, to_date, accept: str, geofence_id: int | None = None):
	"""Shared implementation for the three native export formats.

	Returns the raw response text/bytes plus a suggested filename and
	content type - callers (whitelisted methods) turn this into a Frappe
	file download. Never rebuilds these formats client-side (Section 15/39:
	prefer native export endpoints over regenerating them).
	"""
	if not device_id or not from_date or not to_date:
		raise TraccarError("Device, From, and To are required for export.", 400)

	params = {
		"deviceId": int(device_id),
		"from": to_iso8601(from_date),
		"to": to_iso8601(to_date),
	}
	if geofence_id:
		params["geofenceId"] = int(geofence_id)

	# These formats return non-JSON bodies, so we go through request()
	# directly (not request_safe) and let the caller (a whitelisted method)
	# translate a raised TraccarError into a user-facing frappe.throw.
	client = TraccarClient()
	result = client.request("GET", endpoint_key, params=params, accept=accept)
	return result["data"]


def export_positions_csv(device_id: int, from_date, to_date) -> str:
	return _export("positions_csv", device_id, from_date, to_date, accept="text/csv")


def export_positions_kml(device_id: int, from_date, to_date) -> str:
	return _export(
		"positions_kml", device_id, from_date, to_date, accept="application/vnd.google-earth.kml+xml"
	)


def export_positions_gpx(device_id: int, from_date, to_date) -> str:
	return _export("positions_gpx", device_id, from_date, to_date, accept="application/gpx+xml")


def _client_error(message: str) -> dict:
	return {
		"success": False,
		"data": None,
		"message": message,
		"status_code": 400,
		"error": "TraccarClientValidationError",
	}
