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
