"""Calendars feature module (Section 29).

The spec defines full CRUD for /calendars. Section 29 asks the Calendars
page to display "Schedule" and "Timezone" columns, but the actual Calendar
schema in the OpenAPI spec only has: id, name, data (base64-encoded
iCalendar), attributes - there is no separate schedule or timezone field.
Per Section 50 ("do not assume response fields"), this module exposes
exactly what the spec defines; the "schedule" is the decoded iCalendar
`data` blob itself (timezone, if any, is embedded inside that iCalendar
data as a VTIMEZONE block, not a queryable field). The Calendars page
decodes `data` client-side for a readable preview instead of inventing a
"timezone" field that doesn't exist on the wire.

Manager-only (see permissions note in api.py): Calendars are consumed by
Notifications and Geofences for scheduling, and - unlike Devices/Groups -
don't appear anywhere in the Section 46 navigation for non-Manager roles.
"""

from __future__ import annotations

import base64

import frappe

from .client import TraccarClient
from .utils import paginate_params

CACHE_TTL_SECONDS = 300  # calendars change rarely


def get_calendars(keyword: str | None = None, limit: int | None = None, offset: int | None = None, refresh: bool = False) -> dict:
	cache_key = f"erp_tracking:calendars:{keyword}:{limit}:{offset}"

	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached

	params = paginate_params(limit, offset)
	if keyword:
		params["keyword"] = keyword

	result = TraccarClient().request_safe("GET", "calendars", params=params)
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)
	return result


def get_calendar(calendar_id: int) -> dict:
	return TraccarClient().request_safe("GET", "calendar", path_params={"id": calendar_id})


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:calendars:")


def _encode_ical(ical_text: str) -> str:
	return base64.b64encode(ical_text.encode("utf-8")).decode("ascii")


def create_calendar(name: str, ical_data: str, attributes: dict | None = None) -> dict:
	"""ical_data is raw iCalendar text (e.g. starting with BEGIN:VCALENDAR);
	this base64-encodes it per the schema's `data` field description.
	"""
	payload = {"name": name, "data": _encode_ical(ical_data)}
	if attributes:
		payload["attributes"] = attributes

	result = TraccarClient().request_safe("POST", "calendars", json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def update_calendar(calendar_id: int, name: str | None = None, ical_data: str | None = None, attributes: dict | None = None) -> dict:
	payload = {"id": int(calendar_id)}
	if name is not None:
		payload["name"] = name
	if ical_data is not None:
		payload["data"] = _encode_ical(ical_data)
	if attributes is not None:
		payload["attributes"] = attributes

	result = TraccarClient().request_safe("PUT", "calendar", path_params={"id": calendar_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def delete_calendar(calendar_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "calendar", path_params={"id": calendar_id})
	if result["success"]:
		_invalidate_cache()
	return result
