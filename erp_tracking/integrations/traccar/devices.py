"""Devices feature module (Section 10-11).

Thin wrapper around TraccarClient for the /devices endpoints. All auth and
HTTP handling is already centralized in client.py/auth.py - this module
only knows about the /devices shape and caching policy.
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

# Short TTL: device status/position changes constantly, so this cache only
# exists to absorb bursts of repeated calls (e.g. dashboard + list page
# loading within the same second), not to serve stale fleet state.
CACHE_TTL_SECONDS = 20


def _cache_key(keyword, limit, offset) -> str:
	return f"erp_tracking:devices:{keyword}:{limit}:{offset}"


def get_devices(keyword: str | None = None, limit: int | None = None, offset: int | None = None, refresh: bool = False) -> dict:
	"""List devices, matching GET /devices (Section 10).

	Keyword searches name/uniqueId/phone/model/contact server-side, per the
	OpenAPI spec's description for the `keyword` parameter - no client-side
	filtering is done here.
	"""
	cache_key = _cache_key(keyword, limit, offset)

	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached

	params = paginate_params(limit, offset)
	if keyword:
		params["keyword"] = keyword

	result = TraccarClient().request_safe("GET", "devices", params=params)

	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)

	return result


def get_device(device_id: int) -> dict:
	"""Fetch a single device, matching GET /devices/{id} (Section 11)."""
	return TraccarClient().request_safe("GET", "device", path_params={"id": device_id})


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:devices:")


def create_device(name: str, unique_id: str, category: str | None = None, model: str | None = None, phone: str | None = None, contact: str | None = None, group_id: int | None = None, disabled: bool = False, attributes: dict | None = None) -> dict:
	"""POST /devices. The spec's Device schema requires name + uniqueId;
	everything else here is optional, matching the fields Section 10's
	table actually displays.
	"""
	payload = {"name": name, "uniqueId": unique_id, "disabled": bool(disabled)}
	if category:
		payload["category"] = category
	if model:
		payload["model"] = model
	if phone:
		payload["phone"] = phone
	if contact:
		payload["contact"] = contact
	if group_id:
		payload["groupId"] = int(group_id)
	if attributes:
		payload["attributes"] = attributes

	result = TraccarClient().request_safe("POST", "devices", json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def update_device(device_id: int, **fields) -> dict:
	payload = {"id": int(device_id), **fields}
	result = TraccarClient().request_safe("PUT", "device", path_params={"id": device_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def delete_device(device_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "device", path_params={"id": device_id})
	if result["success"]:
		_invalidate_cache()
	return result


def count_devices() -> dict:
	"""Helper for the Dashboard (Section 36): total/online/offline counts.

	Traccar has no dedicated count endpoint, so this fetches the (already
	cached) device list and counts client-side. Cheap because the list
	itself is small for typical fleets and already cached above.
	"""
	result = get_devices()
	if not result["success"]:
		return result

	devices = result["data"] or []
	online = sum(1 for d in devices if d.get("status") == "online")
	offline = sum(1 for d in devices if d.get("status") != "online")

	return {
		"success": True,
		"data": {"total": len(devices), "online": online, "offline": offline},
		"message": "OK",
		"status_code": result["status_code"],
		"error": None,
	}
