"""Users feature module (Section 13).

IMPORTANT: the Traccar `User` schema in the OpenAPI spec includes a
`password` property. Real Traccar servers do not normally populate it on
read, but this module strips it defensively before the payload is cached
or returned to the browser, so a future Traccar version (or a
misconfigured server) can never leak a credential through this app
(Section 41: never place credentials in an API response).
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

CACHE_TTL_SECONDS = 60

_STRIP_FIELDS = ("password",)


def _redact(user: dict) -> dict:
	return {k: v for k, v in user.items() if k not in _STRIP_FIELDS}


def get_users(keyword: str | None = None, limit: int | None = None, offset: int | None = None, refresh: bool = False) -> dict:
	"""List users, matching GET /users (Section 13)."""
	cache_key = f"erp_tracking:users:{keyword}:{limit}:{offset}"

	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached

	params = paginate_params(limit, offset)
	if keyword:
		params["keyword"] = keyword

	result = TraccarClient().request_safe("GET", "users", params=params)

	if result["success"] and result["data"]:
		result["data"] = [_redact(u) for u in result["data"]]
		frappe.cache().set_value(cache_key, result, expires_in_sec=CACHE_TTL_SECONDS)

	return result


def get_user(user_id: int) -> dict:
	"""Fetch a single user, matching GET /users/{id}."""
	result = TraccarClient().request_safe("GET", "user", path_params={"id": user_id})
	if result["success"] and result["data"]:
		result["data"] = _redact(result["data"])
	return result


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:users:")


def create_user(name: str, email: str, password: str, administrator: bool = False, disabled: bool = False, phone: str | None = None, device_limit: int | None = None) -> dict:
	"""POST /users. A password is required to create a Traccar login - it
	is sent to Traccar (over the same server-side authenticated request as
	every other write in this app) and is never echoed back: create_user's
	response is passed straight through request_safe without redaction
	needed here, since Traccar's create response for this call doesn't
	reflect the plaintext password back - but if a future server version
	did, _redact would still strip it, same as get_user/get_users.
	"""
	payload = {
		"name": name,
		"email": email,
		"password": password,
		"administrator": bool(administrator),
		"disabled": bool(disabled),
	}
	if phone:
		payload["phone"] = phone
	if device_limit is not None:
		payload["deviceLimit"] = int(device_limit)

	result = TraccarClient().request_safe("POST", "users", json=payload)
	if result["success"]:
		_invalidate_cache()
		if result["data"]:
			result["data"] = _redact(result["data"])
	return result


def update_user(user_id: int, password: str | None = None, **fields) -> dict:
	"""PUT /users/{id}. `password` is optional here and, per Section 41,
	deliberately write-only: the edit form never pre-fills it from a GET,
	and it's only included in the outgoing payload when the caller
	actually provided a new one - an empty/omitted password leaves the
	existing one untouched on the Traccar side rather than blanking it.
	"""
	payload = {"id": int(user_id), **fields}
	if password:
		payload["password"] = password

	result = TraccarClient().request_safe("PUT", "user", path_params={"id": user_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
		if result["data"]:
			result["data"] = _redact(result["data"])
	return result


def delete_user(user_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "user", path_params={"id": user_id})
	if result["success"]:
		_invalidate_cache()
	return result


def count_users() -> dict:
	result = get_users()
	if not result["success"]:
		return result
	return {
		"success": True,
		"data": {"total": len(result["data"] or [])},
		"message": "OK",
		"status_code": result["status_code"],
		"error": None,
	}
