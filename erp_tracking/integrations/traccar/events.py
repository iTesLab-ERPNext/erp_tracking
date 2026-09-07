"""Events.

The Traccar specification has **no** ``GET /events`` collection endpoint - only
``GET /events/{id}``.  Event lists therefore come from ``GET /reports/events``,
which is the documented way to query events over a time window.
"""

from frappe.utils import cint, cstr

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.devices import device_map
from erp_tracking.integrations.traccar.reports import fetch_report
from erp_tracking.integrations.traccar.utils import (
	paginate,
	require,
	sort_rows,
	standard_response,
	stringify_attributes,
)

# Badge colour per event family, used by the desk pages.
EVENT_BADGES = {
	"deviceOnline": "green",
	"deviceOffline": "gray",
	"deviceMoving": "blue",
	"deviceStopped": "orange",
	"deviceOverspeed": "red",
	"deviceFuelDrop": "red",
	"deviceInactive": "gray",
	"deviceUnknown": "gray",
	"commandResult": "blue",
	"geofenceEnter": "green",
	"geofenceExit": "orange",
	"alarm": "red",
	"ignitionOn": "green",
	"ignitionOff": "gray",
	"maintenance": "orange",
	"textMessage": "blue",
	"driverChanged": "blue",
	"media": "blue",
}


def badge_for(event_type):
	return EVENT_BADGES.get(cstr(event_type), "blue")


@standard_response
def list_events(device_ids=None, group_ids=None, event_types=None, from_time=None, to_time=None, limit=None, offset=0, sort_by=None, sort_order="desc"):
	rows = fetch_report(
		"events",
		{
			"deviceId": device_ids,
			"groupId": group_ids,
			"type": event_types or ["%"],
			"from": from_time,
			"to": to_time,
		},
	)

	devices = device_map()
	for row in rows:
		device = devices.get(cint(row.get("deviceId"))) or {}
		row["deviceName"] = device.get("name") or row.get("deviceId")
		row["badge"] = badge_for(row.get("type"))

	rows = stringify_attributes(rows)
	rows = sort_rows(rows, sort_by or "eventTime", sort_order)
	return paginate(rows, limit, offset)


@standard_response
def get_event(event_id):
	event_id = cint(require(event_id, "Event"))
	event = get_client().get(TRACCAR_ENDPOINTS["event"].format(id=event_id)) or {}
	if event:
		event["badge"] = badge_for(event.get("type"))
	return event
