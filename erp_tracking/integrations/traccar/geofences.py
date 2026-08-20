"""Geofences feature module (Section 22).

The spec defines full CRUD for /geofences (GET list, GET/{id}, POST, PUT/{id},
DELETE/{id}), so per Section 22 ("If the API supports create/update/delete,
implement those operations with permissions") this module implements all of
it - list/get are read operations, create/update/delete require the write
role (Section 40/41).
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

CACHE_TTL_SECONDS = 60


def get_geofences(
	keyword: str | None = None,
	device_id: int | None = None,
	group_id: int | None = None,
	limit: int | None = None,
	offset: int | None = None,
	refresh: bool = False,
) -> dict:
	cache_key = f"erp_tracking:geofences:{keyword}:{device_id}:{group_id}:{limit}:{offset}"

	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached

	params = paginate_params(limit, offset)
	if keyword:
		params["keyword"] = keyword
	if device_id:
		params["deviceId"] = int(device_id)
	if group_id:
		params["groupId"] = int(group_id)

	result = TraccarClient().request_safe("GET", "geofences", params=params)

	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)

	return result


def get_geofence(geofence_id: int) -> dict:
	return TraccarClient().request_safe("GET", "geofence", path_params={"id": geofence_id})


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:geofences:")


def create_geofence(name: str, area: str, description: str | None = None, calendar_id: int | None = None) -> dict:
	"""POST /geofences. `area` must be a WKT string per the Geofence schema
	(e.g. "CIRCLE (-27.5 153.0, 500)" or "POLYGON ((...))") - this module
	does not validate or construct WKT, it passes through what the caller
	(the Desk form) collected, matching the spec's schema exactly.
	"""
	payload = {"name": name, "area": area}
	if description:
		payload["description"] = description
	if calendar_id:
		payload["calendarId"] = int(calendar_id)

	result = TraccarClient().request_safe("POST", "geofences", json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def update_geofence(geofence_id: int, **fields) -> dict:
	payload = {"id": int(geofence_id), **fields}
	result = TraccarClient().request_safe("PUT", "geofence", path_params={"id": geofence_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def delete_geofence(geofence_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "geofence", path_params={"id": geofence_id})
	if result["success"]:
		_invalidate_cache()
	return result
