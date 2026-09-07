"""Single source of truth for Traccar endpoints and page/report configuration.

Every path below was verified against the supplied Traccar OpenAPI document
(version 6.14.5).  Nothing in this app may build a Traccar path any other way.

Notable facts taken from the specification, because they shape the app:

*  There is **no** ``GET /events`` collection endpoint.  Only ``GET /events/{id}``
   exists.  Event *lists* must be read from ``GET /reports/events``.
*  ``/positions`` has **no** ``limit``/``offset`` parameters, so history paging is
   done server-side in Python after fetching the time window.
*  Native spreadsheet/e-mail delivery only exists for route, events, summary,
   trips, stops and devices (``/reports/{name}/{type}`` with ``type`` in
   ``xlsx|mail``).  There is no PDF endpoint anywhere, so PDF is rendered by
   Frappe.
*  ``daily`` is only documented on ``/reports/summary/{type}``, not on
   ``/reports/summary``.
"""

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
TRACCAR_ENDPOINTS = {
	# Server / system
	"server": "/server",
	"server_geocode": "/server/geocode",
	"server_timezones": "/server/timezones",
	"health": "/health",
	"statistics": "/statistics",
	"audit": "/audit",
	# Session
	"session": "/session",
	"session_token": "/session/token",
	"session_token_revoke": "/session/token/revoke",
	# Fleet
	"devices": "/devices",
	"device": "/devices/{id}",
	"device_accumulators": "/devices/{id}/accumulators",
	"groups": "/groups",
	"group": "/groups/{id}",
	"drivers": "/drivers",
	"driver": "/drivers/{id}",
	"maintenance": "/maintenance",
	"maintenance_item": "/maintenance/{id}",
	"calendars": "/calendars",
	"calendar": "/calendars/{id}",
	"orders": "/orders",
	"order": "/orders/{id}",
	"users": "/users",
	"user": "/users/{id}",
	"permissions": "/permissions",
	# Tracking
	"positions": "/positions",
	"positions_csv": "/positions/csv",
	"positions_gpx": "/positions/gpx",
	"positions_kml": "/positions/kml",
	# Events (single record only - see module docstring)
	"event": "/events/{id}",
	# Reports
	"route_report": "/reports/route",
	"route_report_download": "/reports/route/{type}",
	"events_report": "/reports/events",
	"events_report_download": "/reports/events/{type}",
	"summary_report": "/reports/summary",
	"summary_report_download": "/reports/summary/{type}",
	"trips_report": "/reports/trips",
	"trips_report_download": "/reports/trips/{type}",
	"stops_report": "/reports/stops",
	"stops_report_download": "/reports/stops/{type}",
	"combined_report": "/reports/combined",
	"geofences_report": "/reports/geofences",
	"devices_report_download": "/reports/devices/{type}",
	# Geofences
	"geofences": "/geofences",
	"geofence": "/geofences/{id}",
	# Notifications
	"notifications": "/notifications",
	"notification": "/notifications/{id}",
	"notification_types": "/notifications/types",
	"notificators": "/notifications/notificators",
	"notification_test": "/notifications/test",
	# Commands
	"commands": "/commands",
	"command": "/commands/{id}",
	"command_send": "/commands/send",
	"command_types": "/commands/types",
	# Attributes
	"computed_attributes": "/attributes/computed",
	"computed_attribute": "/attributes/computed/{id}",
	# Live video
	"stream_playlist": "/stream/{deviceId}/{channel}/live.m3u8",
	"stream_segment": "/stream/{deviceId}/{channel}/{index}.ts",
}

# Formats Traccar itself can produce for /reports/{name}/{type}
NATIVE_REPORT_FORMATS = ("xlsx", "mail")

# Formats the app can produce (pdf and csv are rendered by Frappe)
EXPORT_FORMATS = ("csv", "xlsx", "pdf")


# ---------------------------------------------------------------------------
# Generic report engine configuration
# ---------------------------------------------------------------------------
# ``filters``       -> query parameters forwarded to Traccar for the JSON call
# ``download``      -> None when Traccar has no /{type} variant for this report
# ``columns``       -> fieldname / label / fieldtype, straight from the response
#                      schemas in the specification.
REPORT_CONFIG = {
	"summary": {
		"endpoint": TRACCAR_ENDPOINTS["summary_report"],
		"download": TRACCAR_ENDPOINTS["summary_report_download"],
		"label": "Summary",
		"filters": ["deviceId", "groupId", "from", "to"],
		# `daily` is only documented on the /{type} download variant
		"download_only_filters": ["daily"],
		"columns": [
			{"fieldname": "deviceName", "label": "Device", "fieldtype": "Data", "width": 180},
			{"fieldname": "distance", "label": "Distance (m)", "fieldtype": "Float", "width": 130},
			{"fieldname": "averageSpeed", "label": "Average Speed (kn)", "fieldtype": "Float", "width": 150},
			{"fieldname": "maxSpeed", "label": "Maximum Speed (kn)", "fieldtype": "Float", "width": 150},
			{"fieldname": "spentFuel", "label": "Spent Fuel (l)", "fieldtype": "Float", "width": 130},
			{"fieldname": "engineHours", "label": "Engine Hours", "fieldtype": "Int", "width": 120},
		],
	},
	"trips": {
		"endpoint": TRACCAR_ENDPOINTS["trips_report"],
		"download": TRACCAR_ENDPOINTS["trips_report_download"],
		"label": "Trips",
		"filters": ["deviceId", "groupId", "from", "to"],
		"download_only_filters": [],
		"columns": [
			{"fieldname": "deviceName", "label": "Device", "fieldtype": "Data", "width": 160},
			{"fieldname": "startTime", "label": "Start Time", "fieldtype": "Datetime", "width": 160},
			{"fieldname": "endTime", "label": "End Time", "fieldtype": "Datetime", "width": 160},
			{"fieldname": "startAddress", "label": "Start Address", "fieldtype": "Data", "width": 220},
			{"fieldname": "endAddress", "label": "End Address", "fieldtype": "Data", "width": 220},
			{"fieldname": "distance", "label": "Distance (m)", "fieldtype": "Float", "width": 120},
			{"fieldname": "duration", "label": "Duration", "fieldtype": "Duration", "width": 120},
			{"fieldname": "averageSpeed", "label": "Average Speed (kn)", "fieldtype": "Float", "width": 150},
			{"fieldname": "maxSpeed", "label": "Maximum Speed (kn)", "fieldtype": "Float", "width": 150},
			{"fieldname": "spentFuel", "label": "Spent Fuel (l)", "fieldtype": "Float", "width": 120},
			{"fieldname": "driverName", "label": "Driver", "fieldtype": "Data", "width": 140},
		],
	},
	"stops": {
		"endpoint": TRACCAR_ENDPOINTS["stops_report"],
		"download": TRACCAR_ENDPOINTS["stops_report_download"],
		"label": "Stops",
		"filters": ["deviceId", "groupId", "from", "to"],
		"download_only_filters": [],
		"columns": [
			{"fieldname": "deviceName", "label": "Device", "fieldtype": "Data", "width": 160},
			{"fieldname": "startTime", "label": "Start", "fieldtype": "Datetime", "width": 160},
			{"fieldname": "endTime", "label": "End", "fieldtype": "Datetime", "width": 160},
			{"fieldname": "duration", "label": "Duration", "fieldtype": "Duration", "width": 120},
			{"fieldname": "address", "label": "Address", "fieldtype": "Data", "width": 260},
			{"fieldname": "lat", "label": "Latitude", "fieldtype": "Float", "width": 120},
			{"fieldname": "lon", "label": "Longitude", "fieldtype": "Float", "width": 120},
			{"fieldname": "spentFuel", "label": "Spent Fuel (l)", "fieldtype": "Float", "width": 120},
			{"fieldname": "engineHours", "label": "Engine Hours", "fieldtype": "Int", "width": 120},
		],
	},
	"events": {
		"endpoint": TRACCAR_ENDPOINTS["events_report"],
		"download": TRACCAR_ENDPOINTS["events_report_download"],
		"label": "Events",
		"filters": ["deviceId", "groupId", "type", "from", "to"],
		# `alarm` only exists on /reports/events/{type}
		"download_only_filters": ["alarm"],
		"columns": [
			{"fieldname": "eventTime", "label": "Date", "fieldtype": "Datetime", "width": 170},
			{"fieldname": "deviceId", "label": "Device", "fieldtype": "Data", "width": 160},
			{"fieldname": "type", "label": "Event Type", "fieldtype": "Data", "width": 160},
			{"fieldname": "positionId", "label": "Position", "fieldtype": "Int", "width": 100},
			{"fieldname": "geofenceId", "label": "Geofence", "fieldtype": "Int", "width": 100},
			{"fieldname": "maintenanceId", "label": "Maintenance", "fieldtype": "Int", "width": 110},
			{"fieldname": "attributes", "label": "Attributes", "fieldtype": "Data", "width": 240},
		],
	},
	"route": {
		"endpoint": TRACCAR_ENDPOINTS["route_report"],
		"download": TRACCAR_ENDPOINTS["route_report_download"],
		"label": "Route",
		"filters": ["deviceId", "groupId", "from", "to"],
		"download_only_filters": [],
		"columns": [
			{"fieldname": "fixTime", "label": "Time", "fieldtype": "Datetime", "width": 170},
			{"fieldname": "deviceId", "label": "Device", "fieldtype": "Data", "width": 150},
			{"fieldname": "latitude", "label": "Latitude", "fieldtype": "Float", "width": 120},
			{"fieldname": "longitude", "label": "Longitude", "fieldtype": "Float", "width": 120},
			{"fieldname": "speed", "label": "Speed (kn)", "fieldtype": "Float", "width": 110},
			{"fieldname": "course", "label": "Course", "fieldtype": "Float", "width": 100},
			{"fieldname": "address", "label": "Address", "fieldtype": "Data", "width": 260},
		],
	},
	"geofences": {
		"endpoint": TRACCAR_ENDPOINTS["geofences_report"],
		# The specification defines no /reports/geofences/{type} variant.
		"download": None,
		"label": "Geofence Visits",
		"filters": ["deviceId", "groupId", "geofenceId", "from", "to"],
		"download_only_filters": [],
		"columns": [
			{"fieldname": "deviceName", "label": "Device", "fieldtype": "Data", "width": 180},
			{"fieldname": "geofenceId", "label": "Geofence", "fieldtype": "Int", "width": 120},
			{"fieldname": "startTime", "label": "Entered", "fieldtype": "Datetime", "width": 170},
			{"fieldname": "endTime", "label": "Exited", "fieldtype": "Datetime", "width": 170},
		],
	},
}

REPORT_NAMES = tuple(REPORT_CONFIG.keys())


# ---------------------------------------------------------------------------
# Generic list engine configuration
# ---------------------------------------------------------------------------
# ``params`` is the allow-list of query parameters that may be forwarded to
# Traccar for that resource - copied verbatim from the specification.
LIST_CONFIG = {
	"devices": {
		"label": "Devices",
		"endpoint": TRACCAR_ENDPOINTS["devices"],
		"params": ["all", "userId", "id", "uniqueId", "excludeAttributes", "limit", "offset", "keyword"],
		"native_paging": True,
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "name", "label": "Name", "fieldtype": "Data", "width": 180},
			{"fieldname": "uniqueId", "label": "Unique ID", "fieldtype": "Data", "width": 150},
			{"fieldname": "status", "label": "Status", "fieldtype": "Status", "width": 110},
			{"fieldname": "lastUpdate", "label": "Last Update", "fieldtype": "Datetime", "width": 170},
			{"fieldname": "category", "label": "Category", "fieldtype": "Data", "width": 120},
			{"fieldname": "model", "label": "Model", "fieldtype": "Data", "width": 130},
			{"fieldname": "phone", "label": "Phone", "fieldtype": "Data", "width": 130},
			{"fieldname": "disabled", "label": "Disabled", "fieldtype": "Check", "width": 90},
			{"fieldname": "groupId", "label": "Group", "fieldtype": "Int", "width": 100},
		],
	},
	"groups": {
		"label": "Groups",
		"endpoint": TRACCAR_ENDPOINTS["groups"],
		"params": ["all", "userId", "limit", "offset", "keyword"],
		"native_paging": True,
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "name", "label": "Name", "fieldtype": "Data", "width": 260},
			{"fieldname": "groupId", "label": "Parent Group", "fieldtype": "Int", "width": 130},
		],
	},
	"users": {
		"label": "Users",
		"endpoint": TRACCAR_ENDPOINTS["users"],
		"params": ["userId", "limit", "offset", "keyword"],
		"native_paging": True,
		# `password` and `attributes` are deliberately not exposed.
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "name", "label": "Name", "fieldtype": "Data", "width": 180},
			{"fieldname": "email", "label": "Email", "fieldtype": "Data", "width": 220},
			{"fieldname": "phone", "label": "Phone", "fieldtype": "Data", "width": 130},
			{"fieldname": "administrator", "label": "Administrator", "fieldtype": "Check", "width": 120},
			{"fieldname": "readonly", "label": "Readonly", "fieldtype": "Check", "width": 100},
			{"fieldname": "disabled", "label": "Disabled", "fieldtype": "Check", "width": 100},
			{"fieldname": "expirationTime", "label": "Expiration", "fieldtype": "Datetime", "width": 160},
			{"fieldname": "deviceLimit", "label": "Device Limit", "fieldtype": "Int", "width": 110},
			{"fieldname": "userLimit", "label": "User Limit", "fieldtype": "Int", "width": 110},
		],
	},
	"drivers": {
		"label": "Drivers",
		"endpoint": TRACCAR_ENDPOINTS["drivers"],
		"params": ["all", "userId", "deviceId", "groupId", "refresh", "limit", "offset", "keyword"],
		"native_paging": True,
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "name", "label": "Name", "fieldtype": "Data", "width": 220},
			{"fieldname": "uniqueId", "label": "Unique ID", "fieldtype": "Data", "width": 180},
			{"fieldname": "attributes", "label": "Attributes", "fieldtype": "Data", "width": 260},
		],
	},
	"maintenance": {
		"label": "Maintenance",
		"endpoint": TRACCAR_ENDPOINTS["maintenance"],
		"params": ["all", "userId", "deviceId", "groupId", "refresh", "limit", "offset", "keyword"],
		"native_paging": True,
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "name", "label": "Name", "fieldtype": "Data", "width": 220},
			{"fieldname": "type", "label": "Type", "fieldtype": "Data", "width": 160},
			{"fieldname": "start", "label": "Start", "fieldtype": "Float", "width": 130},
			{"fieldname": "period", "label": "Period", "fieldtype": "Float", "width": 130},
			{"fieldname": "attributes", "label": "Attributes", "fieldtype": "Data", "width": 220},
		],
	},
	"calendars": {
		"label": "Calendars",
		"endpoint": TRACCAR_ENDPOINTS["calendars"],
		"params": ["all", "userId", "limit", "offset", "keyword"],
		"native_paging": True,
		# The Calendar schema only has id / name / data / attributes.
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "name", "label": "Name", "fieldtype": "Data", "width": 240},
			{"fieldname": "summary", "label": "Schedule", "fieldtype": "Data", "width": 320},
			{"fieldname": "timezone", "label": "Timezone", "fieldtype": "Data", "width": 160},
		],
	},
	"orders": {
		"label": "Orders",
		"endpoint": TRACCAR_ENDPOINTS["orders"],
		"params": ["all", "userId", "excludeAttributes", "limit", "offset", "keyword"],
		"native_paging": True,
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "uniqueId", "label": "Unique ID", "fieldtype": "Data", "width": 150},
			{"fieldname": "description", "label": "Description", "fieldtype": "Data", "width": 240},
			{"fieldname": "fromAddress", "label": "From", "fieldtype": "Data", "width": 240},
			{"fieldname": "toAddress", "label": "To", "fieldtype": "Data", "width": 240},
		],
	},
	"notifications": {
		"label": "Notifications",
		"endpoint": TRACCAR_ENDPOINTS["notifications"],
		"params": ["all", "userId", "deviceId", "groupId", "refresh", "limit", "offset", "keyword"],
		"native_paging": True,
		# The Notification schema has no `disabled` field; `always` is the closest.
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "type", "label": "Type", "fieldtype": "Data", "width": 200},
			{"fieldname": "description", "label": "Description", "fieldtype": "Data", "width": 240},
			{"fieldname": "notificators", "label": "Notificators", "fieldtype": "Data", "width": 180},
			{"fieldname": "calendarId", "label": "Calendar", "fieldtype": "Int", "width": 110},
			{"fieldname": "always", "label": "Always", "fieldtype": "Check", "width": 90},
		],
	},
	"commands": {
		"label": "Saved Commands",
		"endpoint": TRACCAR_ENDPOINTS["commands"],
		"params": ["all", "userId", "deviceId", "groupId", "refresh", "limit", "offset", "keyword"],
		"native_paging": True,
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "description", "label": "Description", "fieldtype": "Data", "width": 260},
			{"fieldname": "type", "label": "Type", "fieldtype": "Data", "width": 180},
			{"fieldname": "deviceId", "label": "Device", "fieldtype": "Int", "width": 110},
			{"fieldname": "textChannel", "label": "SMS", "fieldtype": "Check", "width": 80},
			{"fieldname": "attributes", "label": "Parameters", "fieldtype": "Data", "width": 240},
		],
	},
	"geofences": {
		"label": "Geofences",
		"endpoint": TRACCAR_ENDPOINTS["geofences"],
		"params": ["all", "userId", "deviceId", "groupId", "refresh", "limit", "offset", "keyword"],
		"native_paging": True,
		"columns": [
			{"fieldname": "id", "label": "ID", "fieldtype": "Int", "width": 70},
			{"fieldname": "name", "label": "Name", "fieldtype": "Data", "width": 200},
			{"fieldname": "description", "label": "Description", "fieldtype": "Data", "width": 240},
			{"fieldname": "shape", "label": "Type", "fieldtype": "Data", "width": 120},
			{"fieldname": "area", "label": "Area", "fieldtype": "Data", "width": 320},
			{"fieldname": "calendarId", "label": "Calendar", "fieldtype": "Int", "width": 110},
		],
	},
}

LIST_RESOURCES = tuple(LIST_CONFIG.keys())

# Columns used when exporting live positions / position history.
POSITION_COLUMNS = [
	{"fieldname": "deviceName", "label": "Device", "fieldtype": "Data", "width": 170},
	{"fieldname": "fixTime", "label": "Time", "fieldtype": "Datetime", "width": 170},
	{"fieldname": "latitude", "label": "Latitude", "fieldtype": "Float", "width": 120},
	{"fieldname": "longitude", "label": "Longitude", "fieldtype": "Float", "width": 120},
	{"fieldname": "speed", "label": "Speed (kn)", "fieldtype": "Float", "width": 110},
	{"fieldname": "course", "label": "Course", "fieldtype": "Float", "width": 100},
	{"fieldname": "altitude", "label": "Altitude (m)", "fieldtype": "Float", "width": 120},
	{"fieldname": "accuracy", "label": "Accuracy (m)", "fieldtype": "Float", "width": 120},
	{"fieldname": "address", "label": "Address", "fieldtype": "Data", "width": 280},
]

AUDIT_COLUMNS = [
	{"fieldname": "actionTime", "label": "Date", "fieldtype": "Datetime", "width": 170},
	{"fieldname": "userEmail", "label": "User", "fieldtype": "Data", "width": 220},
	{"fieldname": "actionType", "label": "Action", "fieldtype": "Data", "width": 140},
	{"fieldname": "objectType", "label": "Object", "fieldtype": "Data", "width": 160},
	{"fieldname": "objectId", "label": "Object ID", "fieldtype": "Int", "width": 110},
	{"fieldname": "address", "label": "Client Address", "fieldtype": "Data", "width": 160},
]
