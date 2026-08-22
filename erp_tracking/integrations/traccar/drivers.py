"""Drivers feature module (Section 27).

The spec defines full CRUD for /drivers (same shape as Groups/Geofences),
so this implements list/get/create/update/delete, matching the pattern
already used in groups.py and geofences.py.
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

CACHE_TTL_SECONDS = 60


def get_drivers(
	keyword: str | None = None,
	device_id: int | None = None,
	group_id: int | None = None,
	limit: int | None = None,
	offset: int | None = None,
	refresh: bool = False,
) -> dict:
	cache_key = f"erp_tracking:drivers:{keyword}:{device_id}:{group_id}:{limit}:{offset}"

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

	result = TraccarClient().request_safe("GET", "drivers", params=params)
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)
	return result


def get_driver(driver_id: int) -> dict:
	return TraccarClient().request_safe("GET", "driver", path_params={"id": driver_id})


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:drivers:")


def create_driver(name: str, unique_id: str, attributes: dict | None = None) -> dict:
	payload = {"name": name, "uniqueId": unique_id}
	if attributes:
		payload["attributes"] = attributes

	result = TraccarClient().request_safe("POST", "drivers", json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def update_driver(driver_id: int, **fields) -> dict:
	payload = {"id": int(driver_id), **fields}
	result = TraccarClient().request_safe("PUT", "driver", path_params={"id": driver_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def delete_driver(driver_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "driver", path_params={"id": driver_id})
	if result["success"]:
		_invalidate_cache()
	return result
