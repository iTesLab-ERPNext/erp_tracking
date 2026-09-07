"""The one HTTP client every Traccar call in this app goes through."""

import time

import frappe
import requests
from frappe import _
from frappe.utils import cint, cstr

from erp_tracking.integrations.traccar.auth import TraccarAuth, get_settings
from erp_tracking.integrations.traccar.exceptions import (
	TraccarAPIError,
	TraccarAuthenticationError,
	TraccarConfigurationError,
	TraccarConnectionError,
	TraccarNotFoundError,
	TraccarPermissionError,
	TraccarRateLimitError,
	TraccarTimeoutError,
)
from erp_tracking.integrations.traccar.utils import redact, validate_path

STATUS_MESSAGES = {
	400: "Traccar rejected the request.",
	401: "Authentication failed.",
	403: "You do not have permission to access this resource.",
	404: "The requested Traccar record was not found.",
	408: "Request timeout.",
	429: "Too many requests to the Traccar server. Please retry shortly.",
	500: "Traccar server error.",
	502: "Traccar server unavailable.",
	503: "Traccar server unavailable.",
	504: "Traccar server timed out.",
}

STATUS_EXCEPTIONS = {
	401: TraccarAuthenticationError,
	403: TraccarPermissionError,
	404: TraccarNotFoundError,
	408: TraccarTimeoutError,
	429: TraccarRateLimitError,
	502: TraccarConnectionError,
	503: TraccarConnectionError,
	504: TraccarTimeoutError,
}


class TraccarClient:
	"""Thin, defensive wrapper around ``requests`` for the Traccar REST API."""

	def __init__(self, settings=None, require_enabled=True):
		self.settings = settings or get_settings()
		if require_enabled and not cint(self.settings.enabled):
			raise TraccarConfigurationError(_("The Traccar integration is disabled."))

		self.auth = TraccarAuth(self.settings)
		self.auth.validate_configuration()

		self.base_url = cstr(self.settings.traccar_url).rstrip("/")
		self.timeout = cint(self.settings.timeout) or 30
		self.verify_ssl = bool(cint(self.settings.verify_ssl))
		self.logger = frappe.logger("erp_tracking", allow_site=True)

	# -- public verbs ----------------------------------------------------
	def get(self, endpoint, params=None, **kwargs):
		return self.request("GET", endpoint, params=params, **kwargs)

	def post(self, endpoint, json_body=None, params=None, data=None, **kwargs):
		return self.request("POST", endpoint, params=params, json_body=json_body, data=data, **kwargs)

	def put(self, endpoint, json_body=None, params=None, **kwargs):
		return self.request("PUT", endpoint, params=params, json_body=json_body, **kwargs)

	def delete(self, endpoint, params=None, json_body=None, **kwargs):
		return self.request("DELETE", endpoint, params=params, json_body=json_body, **kwargs)

	# -- core ------------------------------------------------------------
	def request(
		self,
		method,
		endpoint,
		params=None,
		json_body=None,
		data=None,
		accept="application/json",
		raw=False,
		authenticate=True,
	):
		"""Execute one Traccar request.

		Returns parsed JSON by default, ``(bytes, content_type)`` when
		``raw=True``, and ``None`` for 204 responses.
		"""
		path = validate_path(endpoint)
		url = self.base_url + path

		headers = {"Accept": accept}
		if authenticate:
			headers.update(self.auth.get_auth_headers())

		started = time.monotonic()
		status_code = None
		try:
			response = requests.request(
				method,
				url,
				params=self._clean_params(params),
				json=json_body,
				data=data,
				headers=headers,
				timeout=self.timeout,
				verify=self.verify_ssl,
			)
			status_code = response.status_code
		except requests.Timeout as exc:
			self._log(method, path, 408, started, "TraccarTimeoutError")
			raise TraccarTimeoutError(detail=redact(str(exc)))
		except requests.exceptions.SSLError as exc:
			self._log(method, path, 495, started, "TraccarConnectionError")
			raise TraccarConnectionError(
				_("TLS verification against the Traccar server failed."), 495, redact(str(exc))
			)
		except requests.RequestException as exc:
			self._log(method, path, 0, started, "TraccarConnectionError")
			raise TraccarConnectionError(detail=redact(str(exc)))

		self._log(method, path, status_code, started)
		self._raise_for_status(response)

		if raw:
			return response.content, response.headers.get("Content-Type", "application/octet-stream")

		if response.status_code == 204 or not response.content:
			return None

		if accept.startswith("text/") or "json" not in (response.headers.get("Content-Type") or "json"):
			return response.text

		try:
			return response.json()
		except ValueError:
			return response.text

	def request_raw(self, method, endpoint, params=None, accept="*/*", json_body=None):
		return self.request(
			method, endpoint, params=params, json_body=json_body, accept=accept, raw=True
		)

	# -- helpers ---------------------------------------------------------
	@staticmethod
	def _clean_params(params):
		"""Drop empty values; expand lists into repeated query parameters."""
		if not params:
			return None
		cleaned = {}
		for key, value in params.items():
			if value in (None, "", [], {}):
				continue
			cleaned[key] = value
		return cleaned or None

	def _raise_for_status(self, response):
		if response.status_code < 400:
			return

		status = response.status_code
		message = _(STATUS_MESSAGES.get(status, "Traccar rejected the request."))
		exception = STATUS_EXCEPTIONS.get(status)

		if exception is None:
			exception = TraccarConnectionError if status >= 500 else TraccarAPIError

		# Body may echo request data, so it goes to the log only, redacted.
		raise exception(message, status, redact(response.text))

	def _log(self, method, path, status_code, started, error_type=None):
		"""Log endpoint, method, status, duration and error type - never secrets."""
		self.logger.info(
			{
				"endpoint": path,
				"method": method,
				"status_code": status_code,
				"duration_ms": int((time.monotonic() - started) * 1000),
				"error_type": error_type,
				"user": frappe.session.user,
			}
		)


def get_client(settings=None, require_enabled=True) -> TraccarClient:
	return TraccarClient(settings=settings, require_enabled=require_enabled)
