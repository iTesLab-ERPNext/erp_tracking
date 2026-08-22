"""Orders feature module (Section 34).

The spec defines full CRUD for /orders, same shape as Drivers/Geofences.
No native export endpoint exists for Orders in the spec, so - consistent
with the decision already made for Maintenance in Phase 6 - no Export
button is wired for this resource; only Search/Pagination/Refresh, exactly
what the spec supports.
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

CACHE_TTL_SECONDS = 60


def get_orders(
	keyword: str | None = None,
	user_id: int | None = None,
	exclude_attributes: bool = False,
	limit: int | None = None,
	offset: int | None = None,
	refresh: bool = False,
) -> dict:
	cache_key = f"erp_tracking:orders:{keyword}:{user_id}:{exclude_attributes}:{limit}:{offset}"

	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached

	params = paginate_params(limit, offset)
	if keyword:
		params["keyword"] = keyword
	if user_id:
		params["userId"] = int(user_id)
	if exclude_attributes:
		params["excludeAttributes"] = True

	result = TraccarClient().request_safe("GET", "orders", params=params)
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)
	return result


def get_order(order_id: int) -> dict:
	return TraccarClient().request_safe("GET", "order", path_params={"id": order_id})


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:orders:")


def create_order(unique_id: str, description: str | None = None, from_address: str | None = None, to_address: str | None = None, attributes: dict | None = None) -> dict:
	payload = {"uniqueId": unique_id}
	if description:
		payload["description"] = description
	if from_address:
		payload["fromAddress"] = from_address
	if to_address:
		payload["toAddress"] = to_address
	if attributes:
		payload["attributes"] = attributes

	result = TraccarClient().request_safe("POST", "orders", json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def update_order(order_id: int, **fields) -> dict:
	payload = {"id": int(order_id), **fields}
	result = TraccarClient().request_safe("PUT", "order", path_params={"id": order_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def delete_order(order_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "order", path_params={"id": order_id})
	if result["success"]:
		_invalidate_cache()
	return result
