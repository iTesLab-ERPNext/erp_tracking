"""Maintenance feature module (Section 28).

The spec defines full CRUD for /maintenance, with the same all/userId/
deviceId/groupId/keyword filter set used by Drivers/Notifications/Commands
(the Maintenance schema itself has no deviceId field - devices are linked
via Permission objects server-side - but the list endpoint still accepts
deviceId/groupId as filters, per the spec, so Section 28's "Device filter"
requirement is satisfiable exactly as written).

No native export endpoint exists for Maintenance in the spec (only
/reports/devices/{type}, which is an unrelated device report), so - per
Section 50 - no Export button is wired here; only Search/Pagination/Refresh
as the spec actually supports.
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

CACHE_TTL_SECONDS = 60


def get_maintenance_items(
	keyword: str | None = None,
	device_id: int | None = None,
	group_id: int | None = None,
	limit: int | None = None,
	offset: int | None = None,
	refresh: bool = False,
) -> dict:
	cache_key = f"erp_tracking:maintenance:{keyword}:{device_id}:{group_id}:{limit}:{offset}"

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

	result = TraccarClient().request_safe("GET", "maintenance", params=params)
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)
	return result


def get_maintenance_item(maintenance_id: int) -> dict:
	return TraccarClient().request_safe("GET", "maintenance_item", path_params={"id": maintenance_id})


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:maintenance:")


def create_maintenance_item(name: str, type_: str, start: float, period: float, attributes: dict | None = None) -> dict:
	payload = {"name": name, "type": type_, "start": float(start), "period": float(period)}
	if attributes:
		payload["attributes"] = attributes

	result = TraccarClient().request_safe("POST", "maintenance", json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def update_maintenance_item(maintenance_id: int, **fields) -> dict:
	payload = {"id": int(maintenance_id), **fields}
	result = TraccarClient().request_safe("PUT", "maintenance_item", path_params={"id": maintenance_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def delete_maintenance_item(maintenance_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "maintenance_item", path_params={"id": maintenance_id})
	if result["success"]:
		_invalidate_cache()
	return result
