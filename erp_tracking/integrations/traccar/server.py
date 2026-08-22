"""Server feature module (Sections 30-31).

GET /server and GET /health are marked `security: []` in the OpenAPI spec
- genuinely unauthenticated - so both go through
TraccarClient.request(..., require_auth=False). Every other operation here
(PUT /server, GET /server/geocode, GET /server/timezones) has no security
override in the spec, so it inherits the global BasicAuth/ApiKey
requirement and goes through the normal authenticated path.
"""

from __future__ import annotations

import time

import frappe

from .client import TraccarClient

TIMEZONE_CACHE_TTL_SECONDS = 3600


def get_server_info() -> dict:
	"""GET /server - unauthenticated per the spec."""
	return TraccarClient().request_safe("GET", "server", require_auth=False)


def update_server_info(**fields) -> dict:
	"""PUT /server - requires auth (Manager-only, enforced in api.py)."""
	return TraccarClient().request_safe("PUT", "server", json=fields)


def get_geocode(latitude: float, longitude: float) -> dict:
	"""GET /server/geocode - reverse geocode a coordinate. Requires auth
	(no security override in the spec) even though /server itself doesn't.
	"""
	return TraccarClient().request_safe(
		"GET", "server_geocode", params={"latitude": float(latitude), "longitude": float(longitude)}
	)


def get_timezones(refresh: bool = False) -> dict:
	cache_key = "erp_tracking:timezones"
	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached
	result = TraccarClient().request_safe("GET", "server_timezones")
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=TIMEZONE_CACHE_TTL_SECONDS)
	return result


def get_health() -> dict:
	"""GET /health - unauthenticated per the spec, plain-text "OK" body on
	200 (Section 31). Measures round-trip time client-side for the
	"Response time" display, since the spec doesn't return one itself.
	"""
	started = time.monotonic()
	result = TraccarClient().request_safe("GET", "health", require_auth=False, accept="text/plain")
	result = dict(result)  # avoid mutating a cached/shared dict
	result["response_time_ms"] = round((time.monotonic() - started) * 1000, 1)
	result["healthy"] = result["success"]
	return result
