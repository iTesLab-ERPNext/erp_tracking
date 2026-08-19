"""Central configuration for the Traccar integration.

Two responsibilities live here, deliberately kept together so nothing else
in the app has its own copy of a URL or its own settings-loading code:

1. get_settings() - the single place that reads "Traccar Settings" and
   decrypts secrets. Nothing outside this module (and auth.py, which calls
   it) should call frappe.get_single("Traccar Settings") directly.

2. TRACCAR_ENDPOINTS - the single source of truth for API paths.

Every path below was verified against the supplied OpenAPI spec
(Traccar 6.14.5) operation-by-operation, per Section 50 of the brief.
Two corrections versus a naive reading of the brief's own example map:

  * There is NO "GET /events" list endpoint in the spec. Only:
      - GET /events/{id}      (fetch a single event)
      - GET /reports/events   (fetch events for devices/groups in a time range)
    So the live "Events" page (Section 20) must be built on /reports/events
    with a required time range, not on a bare /events list. This is called
    out again in reports.py / events.py when those modules are implemented.

  * "/commands/types" and "/commands/send" are sub-paths of /commands and
    are listed separately below since they take different parameters.

Do not add a key here without a matching operation in the spec.
"""

from __future__ import annotations

import frappe

TRACCAR_ENDPOINTS = {
	# Server
	"server": "/server",
	"server_geocode": "/server/geocode",
	"server_timezones": "/server/timezones",
	"server_gc": "/server/gc",
	"server_cache": "/server/cache",
	"server_reboot": "/server/reboot",
	"health": "/health",
	"statistics": "/statistics",
	# Session (used only for connection testing / optional session-based auth)
	"session": "/session",
	"session_token": "/session/token",
	"session_token_revoke": "/session/token/revoke",
	# Devices
	"devices": "/devices",
	"device": "/devices/{id}",
	"device_accumulators": "/devices/{id}/accumulators",
	"device_image": "/devices/{id}/image",
	# Groups
	"groups": "/groups",
	"group": "/groups/{id}",
	# Users
	"users": "/users",
	"user": "/users/{id}",
	# Positions
	"positions": "/positions",
	"position": "/positions/{id}",
	"positions_kml": "/positions/kml",
	"positions_csv": "/positions/csv",
	"positions_gpx": "/positions/gpx",
	# Events (single-record fetch only, see module docstring above)
	"event": "/events/{id}",
	# Geofences
	"geofences": "/geofences",
	"geofence": "/geofences/{id}",
	# Notifications
	"notifications": "/notifications",
	"notification": "/notifications/{id}",
	"notification_types": "/notifications/types",
	"notification_notificators": "/notifications/notificators",
	"notification_test": "/notifications/test",
	"notification_test_notificator": "/notifications/test/{notificator}",
	"notification_send_notificator": "/notifications/send/{notificator}",
	# Commands
	"commands": "/commands",
	"command": "/commands/{id}",
	"commands_send": "/commands/send",
	"commands_types": "/commands/types",
	# Drivers
	"drivers": "/drivers",
	"driver": "/drivers/{id}",
	# Maintenance
	"maintenance": "/maintenance",
	"maintenance_item": "/maintenance/{id}",
	# Calendars
	"calendars": "/calendars",
	"calendar": "/calendars/{id}",
	# Computed attributes
	"attributes": "/attributes/computed",
	"attribute": "/attributes/computed/{id}",
	"attributes_test": "/attributes/computed/test",
	# Orders
	"orders": "/orders",
	"order": "/orders/{id}",
	# Audit
	"audit": "/audit",
	# Permissions
	"permissions": "/permissions",
	"permissions_bulk": "/permissions/bulk",
	# Reports
	"reports_combined": "/reports/combined",
	"reports_route": "/reports/route",
	"reports_route_type": "/reports/route/{type}",
	"reports_events": "/reports/events",
	"reports_events_type": "/reports/events/{type}",
	"reports_geofences": "/reports/geofences",
	"reports_summary": "/reports/summary",
	"reports_summary_type": "/reports/summary/{type}",
	"reports_trips": "/reports/trips",
	"reports_trips_type": "/reports/trips/{type}",
	"reports_stops": "/reports/stops",
	"reports_stops_type": "/reports/stops/{type}",
	"reports_devices_type": "/reports/devices/{type}",
	# Stream (HLS live video)
	"stream_playlist": "/stream/{deviceId}/{channel}/live.m3u8",
	"stream_segment": "/stream/{deviceId}/{channel}/{index}.ts",
}

# Endpoints allowed for the generic report engine (Section 37). Anything not
# in this set is rejected by reports.py before a request is ever built -
# this is the "validate report names against an allowed list" control from
# Section 41.
ALLOWED_REPORT_KEYS = {
	"reports_trips",
	"reports_stops",
	"reports_summary",
	"reports_events",
	"reports_route",
	"reports_geofences",
	"reports_combined",
}


def build_path(endpoint_key: str, **path_params) -> str:
	"""Resolve an endpoint key to a concrete path, filling in {placeholders}.

	Raises KeyError if the key is not in TRACCAR_ENDPOINTS, so a typo can
	never silently hit a made-up URL.
	"""
	template = TRACCAR_ENDPOINTS[endpoint_key]
	return template.format(**path_params) if path_params else template


class TraccarSettingsData:
	"""Plain container for the fields the client/auth layer need.

	Keeping this as a small dataclass-like object (instead of passing the
	raw Frappe doc around) means secrets only ever flow through here and
	auth.py - never into devices.py, reports.py, positions.py, etc.
	"""

	__slots__ = (
		"url",
		"enabled",
		"timeout",
		"verify_ssl",
		"auth_type",
		"username",
		"password",
		"api_key",
	)

	def __init__(self, doc):
		self.url = (doc.traccar_url or "").rstrip("/")
		self.enabled = bool(doc.enabled)
		self.timeout = doc.timeout or 15
		self.verify_ssl = bool(doc.verify_ssl)
		self.auth_type = doc.auth_type
		self.username = doc.username
		self.password = doc.get_password("password", raise_exception=False) if doc.auth_type == "Basic Auth" else None
		self.api_key = doc.get_password("api_key", raise_exception=False) if doc.auth_type == "API Key" else None


def get_settings() -> TraccarSettingsData:
	"""Load Traccar Settings (the Single DocType) and return a safe container.

	This is the ONLY function in the whole app that should call
	frappe.get_single("Traccar Settings"). auth.py calls this; client.py
	calls auth.py. Every feature module (devices.py, positions.py, ...)
	only ever talks to TraccarClient, so secrets never travel further than
	this file and auth.py.
	"""
	doc = frappe.get_single("Traccar Settings")
	return TraccarSettingsData(doc)
