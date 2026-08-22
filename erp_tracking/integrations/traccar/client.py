"""Central HTTP client for the Traccar REST API.

Every feature module (devices.py, positions.py, reports.py, commands.py,
...) built in later phases talks to Traccar exclusively through
TraccarClient. This is what Section 7 of the brief calls for: one place
that owns settings loading, authentication, headers, timeouts, error
handling, JSON parsing, and response shape - so nothing gets duplicated
or drifts between modules.
"""

from __future__ import annotations

import time

import frappe
import requests

from .auth import TraccarAuth
from .config import TraccarSettingsData, build_path, get_settings
from .exceptions import (
	TraccarAPIError,
	TraccarAuthenticationError,
	TraccarConfigurationError,
	TraccarConnectionError,
	TraccarTimeoutError,
	status_message,
)

# Fields that must never appear in logs or be echoed back to the client,
# even accidentally via a raised exception or a debug log line.
_SENSITIVE_KEYS = {"password", "api_key", "token", "authorization"}


def _standard_response(
	success: bool,
	data=None,
	message: str = "",
	status_code: int | None = None,
	error: str | None = None,
) -> dict:
	"""Shape every response the same way (Section 8)."""
	return {
		"success": success,
		"data": data,
		"message": message,
		"status_code": status_code,
		"error": error,
	}


def _scrub(value):
	"""Best-effort redaction before anything touches frappe.logger()."""
	if isinstance(value, dict):
		return {
			k: ("***" if k.lower() in _SENSITIVE_KEYS else _scrub(v))
			for k, v in value.items()
		}
	if isinstance(value, list):
		return [_scrub(v) for v in value]
	return value


class TraccarClient:
	"""Thin, safe wrapper around `requests` for the Traccar REST API.

	Usage (from any feature module, in later phases):

		client = TraccarClient()
		result = client.get("devices")               # by endpoint key
		result = client.get("device", path_params={"id": 42})

	`result` is always the standardized dict from _standard_response();
	callers never see a raw requests.Response or a raw exception, so every
	page in the app can render errors the same way.
	"""

	def __init__(self, settings: TraccarSettingsData | None = None):
		self._auth = TraccarAuth(settings)

	# -- public HTTP verbs ---------------------------------------------------

	def get(self, endpoint_key: str, path_params: dict | None = None, params: dict | None = None, **kwargs) -> dict:
		return self.request("GET", endpoint_key, path_params=path_params, params=params, **kwargs)

	def post(self, endpoint_key: str, path_params: dict | None = None, json: dict | None = None, params: dict | None = None, **kwargs) -> dict:
		return self.request("POST", endpoint_key, path_params=path_params, json=json, params=params, **kwargs)

	def put(self, endpoint_key: str, path_params: dict | None = None, json: dict | None = None, params: dict | None = None, **kwargs) -> dict:
		return self.request("PUT", endpoint_key, path_params=path_params, json=json, params=params, **kwargs)

	def delete(self, endpoint_key: str, path_params: dict | None = None, params: dict | None = None, **kwargs) -> dict:
		return self.request("DELETE", endpoint_key, path_params=path_params, params=params, **kwargs)

	# -- core request path ----------------------------------------------------

	def request(
		self,
		method: str,
		endpoint_key: str,
		path_params: dict | None = None,
		params: dict | None = None,
		json: dict | None = None,
		accept: str = "application/json",
		require_auth: bool = True,
	) -> dict:
		"""Perform one Traccar API call and return a standardized response.

		1. Load Traccar Settings (via auth.py, never directly).
		2. Authenticate / build headers - unless require_auth=False.
		3. Resolve the endpoint path from the central config map.
		4. Send the HTTP request with the configured timeout + TLS verification.
		5. Handle timeouts, connection errors, and HTTP error codes.
		6. Parse JSON (or return raw text for non-JSON responses like /health).
		7. Return the standardized response shape. Never raises to the caller.

		require_auth=False is for the two operations the OpenAPI spec marks
		`security: []` - GET /server and GET /health (see server.py). Every
		other endpoint keeps the default (True): the spec's global security
		requirement (BasicAuth or ApiKey) applies to everything else,
		including PUT /server, /server/geocode, /server/timezones,
		/statistics, and /audit, none of which override the global default.
		"""
		started = time.monotonic()
		status_code = None

		try:
			if require_auth:
				settings = self._auth.authenticate()
				headers = {"Accept": accept}
				headers.update(self._auth.get_auth_headers())
			else:
				# Still needs a configured, enabled URL - just skips the
				# credential requirement these two specific endpoints don't need.
				settings = self._auth.settings
				if not settings.url:
					raise TraccarConfigurationError("Traccar server URL is not configured.")
				if not settings.enabled:
					raise TraccarConfigurationError("Traccar integration is disabled.")
				headers = {"Accept": accept}

			url = f"{settings.url}{build_path(endpoint_key, **(path_params or {}))}"

			response = requests.request(
				method=method,
				url=url,
				headers=headers,
				params=params,
				json=json,
				timeout=settings.timeout,
				verify=settings.verify_ssl,
			)
			status_code = response.status_code

			if status_code == 401 or status_code == 403:
				raise TraccarAuthenticationError(status_message(status_code), status_code)

			if status_code >= 400:
				raise TraccarAPIError(status_message(status_code), status_code)

			data = self._parse_body(response)
			return _standard_response(
				success=True,
				data=data,
				message="OK",
				status_code=status_code,
			)

		except requests.exceptions.Timeout:
			self._log("timeout", endpoint_key, method, status_code, started)
			raise TraccarTimeoutError("Request timeout.", 408)

		except requests.exceptions.ConnectionError:
			self._log("connection_error", endpoint_key, method, status_code, started)
			raise TraccarConnectionError("Traccar server unavailable.", 503)

		except (TraccarAuthenticationError, TraccarAPIError, TraccarConfigurationError):
			self._log("api_error", endpoint_key, method, status_code, started)
			raise

	def request_safe(self, *args, **kwargs) -> dict:
		"""Same as request(), but catches TraccarError and returns the
		standardized error shape instead of raising. Whitelisted Frappe
		methods that should never 500 out to the client call this instead
		of request().
		"""
		try:
			return self.request(*args, **kwargs)
		except (
			TraccarConfigurationError,
			TraccarConnectionError,
			TraccarTimeoutError,
			TraccarAuthenticationError,
			TraccarAPIError,
		) as exc:
			return _standard_response(
				success=False,
				data=None,
				message=exc.message,
				status_code=exc.status_code,
				error=type(exc).__name__,
			)

	# -- helpers ---------------------------------------------------------------

	@staticmethod
	def _parse_body(response: "requests.Response"):
		content_type = response.headers.get("Content-Type", "")

		if "application/json" in content_type:
			if not response.content:
				return None
			return response.json()

		if not response.content:
			# e.g. 204 No Content (mail-delivery report requests, DELETE endpoints)
			return None

		if content_type.startswith("text/") or "xml" in content_type or "mpegurl" in content_type:
			# /health (text/plain), /positions/gpx, /positions/kml (+xml),
			# and the HLS playlist (application/vnd.apple.mpegurl) are all
			# textual formats despite that last one not living under text/*
			# or containing "xml" - it still needs response.text, not bytes,
			# or stream.py's playlist line-rewriting would break.
			return response.text

		# Binary payloads - native XLSX report/route downloads, device images,
		# HLS video segments (video/mp2t). Returning raw bytes here (not
		# response.text) matters: decoding a binary spreadsheet or video
		# segment as UTF-8 text would corrupt it before it ever reaches the
		# browser.
		return response.content

	@staticmethod
	def _log(event: str, endpoint_key: str, method: str, status_code, started: float):
		"""Structured logging per Section 43 - never logs secrets, only
		metadata: endpoint, method, status, and execution time.
		"""
		elapsed_ms = round((time.monotonic() - started) * 1000, 1)
		frappe.logger("erp_tracking.traccar").info(
			_scrub(
				{
					"event": event,
					"endpoint": endpoint_key,
					"method": method,
					"status_code": status_code,
					"elapsed_ms": elapsed_ms,
				}
			)
		)
