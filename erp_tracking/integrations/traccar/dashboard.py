"""Dashboard aggregation (Section 36).

Composes counts from the feature modules built so far (devices, groups,
users, geofences, and - since Phase 4 - today's events/trips/stops via the
report engine).

Events Today / Trips Today / Stops Today use the report engine (reports.py).
Traccar's report endpoints require an explicit deviceId or groupId list -
there's no site-wide wildcard - so this passes every known device id at
once (the spec's array param encoding supports that). For very large
fleets that could be slow, so it's capped: past
MAX_DEVICES_FOR_DASHBOARD_REPORTS devices, those three cards report None
rather than either fabricating a number or making the dashboard hang
(Section 49: never substitute fake data).
"""

from __future__ import annotations

import frappe

from .devices import count_devices, get_devices
from .geofences import get_geofences
from .groups import count_groups
from .reports import generate_report
from .users import count_users

CACHE_TTL_SECONDS = 20
MAX_DEVICES_FOR_DASHBOARD_REPORTS = 50


def _today_range():
	now = frappe.utils.now_datetime()
	start = now.replace(hour=0, minute=0, second=0, microsecond=0)
	return start, now


def _today_counts(device_ids: list[int]) -> dict:
	if not device_ids:
		return {"events_today": 0, "trips_today": 0, "stops_today": 0}

	if len(device_ids) > MAX_DEVICES_FOR_DASHBOARD_REPORTS:
		return {"events_today": None, "trips_today": None, "stops_today": None}

	start, now = _today_range()
	counts = {}
	for key, card in (("events", "events_today"), ("trips", "trips_today"), ("stops", "stops_today")):
		result = generate_report(key, device_ids=device_ids, from_date=start, to_date=now)
		counts[card] = len(result["data"] or []) if result["success"] else None
	return counts


def get_dashboard_summary() -> dict:
	devices = count_devices()
	groups = count_groups()
	users = count_users()
	geofences = get_geofences()

	# If the very first call failed on configuration/connection, don't mask
	# it - surface that error as-is so the Dashboard can show the real
	# "Traccar is not configured" / connection-error state (Section 49).
	primary_error = next((r for r in (devices, groups, users, geofences) if not r["success"]), None)
	if primary_error:
		return primary_error

	device_list = get_devices()
	device_ids = [d["id"] for d in (device_list["data"] or [])] if device_list["success"] else []
	today_counts = _today_counts(device_ids)

	return {
		"success": True,
		"data": {
			"devices_total": devices["data"]["total"],
			"devices_online": devices["data"]["online"],
			"devices_offline": devices["data"]["offline"],
			"groups_total": groups["data"]["total"],
			"users_total": users["data"]["total"],
			"geofences_total": len(geofences["data"] or []),
			**today_counts,
		},
		"message": "OK",
		"status_code": 200,
		"error": None,
	}

