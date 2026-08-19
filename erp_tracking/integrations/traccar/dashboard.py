"""Dashboard aggregation (Section 36).

Composes counts from the feature modules that exist so far. Geofences has
no dedicated feature module yet (that lands in Phase 5), so its count is
fetched directly through the generic TraccarClient here - a small,
explicitly-noted exception, not a new pattern to copy elsewhere.

Events Today / Trips Today / Stops Today depend on the Reports engine
(Phase 4, since Traccar's report endpoints require an explicit device/group
+ time range - there's no site-wide "today" count without iterating every
device). Until then this returns those three as unavailable=True so the
Dashboard page can render an honest "—" instead of a fabricated number
(Section 49: never substitute fake data for real API data).
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .devices import count_devices
from .groups import count_groups
from .users import count_users

CACHE_TTL_SECONDS = 20


def get_dashboard_summary() -> dict:
	devices = count_devices()
	groups = count_groups()
	users = count_users()
	geofences = TraccarClient().request_safe("GET", "geofences")

	# If the very first call failed on configuration/connection, don't mask
	# it - surface that error as-is so the Dashboard can show the real
	# "Traccar is not configured" / connection-error state (Section 49).
	primary_error = next((r for r in (devices, groups, users, geofences) if not r["success"]), None)
	if primary_error:
		return primary_error

	return {
		"success": True,
		"data": {
			"devices_total": devices["data"]["total"],
			"devices_online": devices["data"]["online"],
			"devices_offline": devices["data"]["offline"],
			"groups_total": groups["data"]["total"],
			"users_total": users["data"]["total"],
			"geofences_total": len(geofences["data"] or []),
			"events_today": None,  # available once reports.py lands (Phase 4)
			"trips_today": None,
			"stops_today": None,
		},
		"message": "OK",
		"status_code": 200,
		"error": None,
	}
