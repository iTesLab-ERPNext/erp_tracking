"""Notifications feature module (Section 23).

The spec defines full CRUD for /notifications, plus /notifications/types
(available notification types), /notifications/notificators (available
delivery channels), and test-send endpoints. Section 23 says "Implement
CRUD only if supported by the provided API specification" - it is, so this
implements all of it.
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

CACHE_TTL_SECONDS = 60
# Types/notificators change essentially never at runtime - cache much longer.
REFERENCE_CACHE_TTL_SECONDS = 3600


def get_notifications(
	keyword: str | None = None,
	device_id: int | None = None,
	group_id: int | None = None,
	limit: int | None = None,
	offset: int | None = None,
	refresh: bool = False,
) -> dict:
	cache_key = f"erp_tracking:notifications:{keyword}:{device_id}:{group_id}:{limit}:{offset}"

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

	result = TraccarClient().request_safe("GET", "notifications", params=params)
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)
	return result


def get_notification(notification_id: int) -> dict:
	return TraccarClient().request_safe("GET", "notification", path_params={"id": notification_id})


def get_notification_types(refresh: bool = False) -> dict:
	cache_key = "erp_tracking:notification_types"
	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached
	result = TraccarClient().request_safe("GET", "notification_types")
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=REFERENCE_CACHE_TTL_SECONDS)
	return result


def get_notificators(announcement: bool | None = None, refresh: bool = False) -> dict:
	cache_key = f"erp_tracking:notificators:{announcement}"
	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached
	params = {}
	if announcement is not None:
		params["announcement"] = bool(announcement)
	result = TraccarClient().request_safe("GET", "notification_notificators", params=params)
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=REFERENCE_CACHE_TTL_SECONDS)
	return result


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:notifications:")


def create_notification(type_: str, notificators: str, description: str | None = None, always: bool = False, calendar_id: int | None = None) -> dict:
	payload = {"type": type_, "notificators": notificators, "always": bool(always)}
	if description:
		payload["description"] = description
	if calendar_id:
		payload["calendarId"] = int(calendar_id)

	result = TraccarClient().request_safe("POST", "notifications", json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def update_notification(notification_id: int, **fields) -> dict:
	payload = {"id": int(notification_id), **fields}
	result = TraccarClient().request_safe("PUT", "notification", path_params={"id": notification_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def delete_notification(notification_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "notification", path_params={"id": notification_id})
	if result["success"]:
		_invalidate_cache()
	return result


def send_test_notification() -> dict:
	"""POST /notifications/test - sends to the current (Traccar) user via
	email and SMS, per the spec. Returns success=True on 204.
	"""
	return TraccarClient().request_safe("POST", "notification_test")
