"""Server information, health and geocoding."""

import time

import frappe
import requests
from frappe import _
from frappe.utils import cint, cstr, now_datetime

from erp_tracking.integrations.traccar.auth import get_settings
from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.utils import cached, redact, standard_response

# Fields from the Server schema that are safe to show in the desk.
# `bingKey` is deliberately excluded - it is a third-party credential.
PUBLIC_SERVER_FIELDS = (
	"id",
	"version",
	"registration",
	"readonly",
	"deviceReadonly",
	"limitCommands",
	"map",
	"mapUrl",
	"poiLayer",
	"announcement",
	"latitude",
	"longitude",
	"zoom",
	"forceSettings",
	"coordinateFormat",
	"openIdEnabled",
	"openIdForce",
)


@standard_response
def get_server_info(refresh=False):
	def _call():
		return get_client().get(TRACCAR_ENDPOINTS["server"]) or {}

	ttl = cint(frappe.get_cached_value("Traccar Settings", None, "cache_ttl")) or 300
	info = cached(("server_info",), ttl, _call, refresh)
	return {k: v for k, v in (info or {}).items() if k in PUBLIC_SERVER_FIELDS}


@standard_response
def get_timezones(refresh=False):
	def _call():
		return get_client().get(TRACCAR_ENDPOINTS["server_timezones"]) or []

	return cached(("timezones",), 86400, _call, refresh)


@standard_response
def reverse_geocode(latitude, longitude):
	return get_client().get(
		TRACCAR_ENDPOINTS["server_geocode"],
		{"latitude": float(latitude), "longitude": float(longitude)},
		accept="text/plain",
	)


@standard_response
def check_health():
	"""GET /health.

	The endpoint is declared with ``security: []``, so it is called without an
	Authorization header - it is a pure uptime probe.
	"""
	settings = get_settings()
	base_url = cstr(settings.traccar_url).rstrip("/")
	if not base_url:
		from erp_tracking.integrations.traccar.exceptions import TraccarConfigurationError

		raise TraccarConfigurationError(_("Traccar server URL is not set."))

	url = base_url + TRACCAR_ENDPOINTS["health"]
	started = time.monotonic()
	logger = frappe.logger("erp_tracking", allow_site=True)

	try:
		response = requests.get(
			url,
			headers={"Accept": "text/plain"},
			timeout=cint(settings.timeout) or 30,
			verify=bool(cint(settings.verify_ssl)),
		)
		elapsed = int((time.monotonic() - started) * 1000)
		healthy = response.status_code == 200
		logger.info(
			{
				"endpoint": TRACCAR_ENDPOINTS["health"],
				"method": "GET",
				"status_code": response.status_code,
				"duration_ms": elapsed,
			}
		)
		return {
			"healthy": healthy,
			"status": (response.text or "").strip()[:100] if healthy else "",
			"status_code": response.status_code,
			"response_time_ms": elapsed,
			"checked_at": cstr(now_datetime()),
		}
	except requests.RequestException as exc:
		elapsed = int((time.monotonic() - started) * 1000)
		logger.warning(
			{
				"endpoint": TRACCAR_ENDPOINTS["health"],
				"method": "GET",
				"status_code": 0,
				"duration_ms": elapsed,
				"error_type": type(exc).__name__,
				"detail": redact(str(exc)),
			}
		)
		return {
			"healthy": False,
			"status": "",
			"status_code": 0,
			"response_time_ms": elapsed,
			"checked_at": cstr(now_datetime()),
		}
