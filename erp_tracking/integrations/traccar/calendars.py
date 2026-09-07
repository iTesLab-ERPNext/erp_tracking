"""Calendars - GET /calendars and /calendars/{id}.

The Calendar schema only carries ``id``, ``name``, ``data`` (base64 iCalendar)
and ``attributes``.  The list engine derives a readable schedule and timezone
from the iCalendar blob rather than inventing fields.
"""

from frappe.utils import cint

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import _describe_icalendar, fetch_all, fetch_list
from erp_tracking.integrations.traccar.utils import require, standard_response


@standard_response
def list_calendars(filters=None, refresh=False):
	return fetch_list("calendars", filters=filters, refresh=refresh)


@standard_response
def get_calendar(calendar_id):
	calendar_id = cint(require(calendar_id, "Calendar"))
	calendar = get_client().get(TRACCAR_ENDPOINTS["calendar"].format(id=calendar_id)) or {}
	summary, timezone = _describe_icalendar(calendar.get("data"))
	calendar["summary"] = summary
	calendar["timezone"] = timezone
	calendar.pop("data", None)
	return calendar


def calendar_choices():
	return [{"value": cint(c.get("id")), "label": c.get("name")} for c in fetch_all("calendars")]
