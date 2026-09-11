"""Calendars - full CRUD over /calendars and /calendars/{id}.

The Calendar schema only carries ``id``, ``name``, ``data`` (base64
iCalendar) and ``attributes``.  The list engine derives a readable schedule
and timezone from the iCalendar blob rather than inventing fields; this
module additionally exposes the *decoded* iCalendar text as ``ical_text`` on
:func:`get_calendar` (not the raw base64) so the edit dialog can prefill and
re-save it, then re-encodes it to base64 before it ever reaches Traccar.
"""

import base64

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
	raw = calendar.get("data")
	summary, timezone = _describe_icalendar(raw)
	calendar["summary"] = summary
	calendar["timezone"] = timezone
	calendar["ical_text"] = _decode_icalendar(raw)
	calendar.pop("data", None)
	return calendar


def _decode_icalendar(data):
	if not data:
		return ""
	try:
		return base64.b64decode(data).decode("utf-8", errors="ignore")
	except Exception:  # noqa: BLE001
		return ""


def _encode_icalendar(text):
	return base64.b64encode((text or "").encode("utf-8")).decode("ascii")


@standard_response
def create_calendar(payload):
	payload = dict(payload or {})
	ical_text = payload.pop("ical_text", None)
	payload["data"] = _encode_icalendar(ical_text)
	return get_client().post(TRACCAR_ENDPOINTS["calendars"], json_body=payload)


@standard_response
def update_calendar(calendar_id, payload):
	calendar_id = cint(require(calendar_id, "Calendar"))
	payload = dict(payload or {})
	payload["id"] = calendar_id
	if "ical_text" in payload:
		payload["data"] = _encode_icalendar(payload.pop("ical_text"))
	return get_client().put(TRACCAR_ENDPOINTS["calendar"].format(id=calendar_id), json_body=payload)


@standard_response
def delete_calendar(calendar_id):
	calendar_id = cint(require(calendar_id, "Calendar"))
	get_client().delete(TRACCAR_ENDPOINTS["calendar"].format(id=calendar_id))
	return {"deleted": calendar_id}


def calendar_choices():
	return [{"value": cint(c.get("id")), "label": c.get("name")} for c in fetch_all("calendars")]
