"""Groups feature module (Section 12)."""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

CACHE_TTL_SECONDS = 60  # groups change far less often than device status


def get_groups(keyword: str | None = None, limit: int | None = None, offset: int | None = None, refresh: bool = False) -> dict:
	"""List groups, matching GET /groups."""
	cache_key = f"erp_tracking:groups:{keyword}:{limit}:{offset}"

	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached

	params = paginate_params(limit, offset)
	if keyword:
		params["keyword"] = keyword

	result = TraccarClient().request_safe("GET", "groups", params=params)

	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)

	return result


def get_group(group_id: int) -> dict:
	"""Fetch a single group, matching GET /groups/{id}."""
	return TraccarClient().request_safe("GET", "group", path_params={"id": group_id})


def count_groups() -> dict:
	result = get_groups()
	if not result["success"]:
		return result
	return {
		"success": True,
		"data": {"total": len(result["data"] or [])},
		"message": "OK",
		"status_code": result["status_code"],
		"error": None,
	}


def devices_in_group(group_id: int) -> dict:
	"""Devices belonging to a group (Section 12: "Devices in group").

	The /devices endpoint itself has no groupId filter in the spec, so this
	fetches the full device list and filters client-side on groupId. Kept
	here (not in devices.py) since it's a Groups-page concern.
	"""
	from .devices import get_devices

	result = get_devices()
	if not result["success"]:
		return result

	devices = [d for d in (result["data"] or []) if d.get("groupId") == group_id]
	return {
		"success": True,
		"data": devices,
		"message": "OK",
		"status_code": result["status_code"],
		"error": None,
	}
