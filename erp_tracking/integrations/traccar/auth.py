"""Centralised Traccar authentication.

This is the *only* module in the app that reads credentials.  Neither
``client.py`` nor any resource module (devices, reports, ...) touches the
password or API key directly - they all ask :class:`TraccarAuth` for headers.

Supported schemes, both declared in the Traccar OpenAPI ``securitySchemes``:

* ``BasicAuth`` - HTTP Basic with the Traccar user's e-mail and password.
* ``ApiKey``    - HTTP Bearer with a Traccar API token.
"""

import base64

import frappe
import requests
from frappe import _
from frappe.utils import cint, cstr

from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.exceptions import (
	TraccarAuthenticationError,
	TraccarConfigurationError,
	TraccarConnectionError,
	TraccarTimeoutError,
)
from erp_tracking.integrations.traccar.utils import cache_key, redact

AUTH_BASIC = "Basic Auth"
AUTH_API_KEY = "API Key"

SESSION_VALIDATION_TTL = 300  # seconds


def get_settings():
	"""Return the Traccar Settings single doc (server-side only)."""
	return frappe.get_cached_doc("Traccar Settings")


class TraccarAuth:
	def __init__(self, settings=None):
		self.settings = settings or get_settings()
		self.auth_type = self.settings.auth_type or AUTH_BASIC
		self.base_url = cstr(self.settings.traccar_url).rstrip("/")

	# -- configuration ---------------------------------------------------
	def validate_configuration(self):
		if not self.base_url:
			raise TraccarConfigurationError(_("Traccar server URL is not set."))
		if not self.base_url.startswith(("http://", "https://")):
			raise TraccarConfigurationError(_("Traccar server URL must start with http:// or https://."))

		if self.auth_type == AUTH_API_KEY:
			if not self._api_key():
				raise TraccarConfigurationError(_("Traccar API key is not set."))
		else:
			if not self.settings.username or not self._password():
				raise TraccarConfigurationError(_("Traccar username or password is not set."))

	# -- secret access (never leaves this class) -------------------------
	def _password(self):
		try:
			return self.settings.get_password("password", raise_exception=False)
		except Exception:  # noqa: BLE001
			return None

	def _api_key(self):
		try:
			return self.settings.get_password("api_key", raise_exception=False)
		except Exception:  # noqa: BLE001
			return None

	# -- headers ---------------------------------------------------------
	def get_auth_headers(self) -> dict:
		"""Build the Authorization header for an outbound Traccar request."""
		self.validate_configuration()

		if self.auth_type == AUTH_API_KEY:
			return {"Authorization": f"Bearer {self._api_key()}"}

		raw = f"{cstr(self.settings.username)}:{cstr(self._password())}".encode()
		return {"Authorization": "Basic " + base64.b64encode(raw).decode()}

	# -- session ---------------------------------------------------------
	def authenticate(self) -> dict:
		"""Verify the configured credentials against Traccar.

		Returns the sanitised Traccar user record.  Raises
		:class:`TraccarAuthenticationError` when the credentials are rejected.
		"""
		self.validate_configuration()
		url = self.base_url + TRACCAR_ENDPOINTS["session"]
		timeout = cint(self.settings.timeout) or 30
		verify = bool(cint(self.settings.verify_ssl))

		try:
			if self.auth_type == AUTH_API_KEY:
				response = requests.get(
					url,
					headers={**self.get_auth_headers(), "Accept": "application/json"},
					timeout=timeout,
					verify=verify,
				)
			else:
				# POST /session with form credentials is the documented login call.
				response = requests.post(
					url,
					data={
						"email": cstr(self.settings.username),
						"password": cstr(self._password()),
					},
					headers={"Accept": "application/json"},
					timeout=timeout,
					verify=verify,
				)
		except requests.Timeout as exc:
			raise TraccarTimeoutError(detail=redact(str(exc)))
		except requests.exceptions.SSLError as exc:
			raise TraccarConnectionError(
				_("TLS verification against the Traccar server failed."), 495, redact(str(exc))
			)
		except requests.RequestException as exc:
			raise TraccarConnectionError(detail=redact(str(exc)))

		if response.status_code in (401, 403):
			raise TraccarAuthenticationError(status_code=response.status_code)
		if response.status_code >= 500:
			raise TraccarConnectionError(status_code=response.status_code)
		if response.status_code >= 400:
			raise TraccarAuthenticationError(
				_("Traccar rejected the credentials."), response.status_code, redact(response.text)
			)

		try:
			user = response.json() or {}
		except ValueError:
			user = {}

		self._mark_validated()
		return self.sanitize_user(user)

	def validate_session(self, refresh=False) -> bool:
		"""Cheap cached credential check used before batches of requests."""
		key = self._cache_key()
		if not refresh:
			cached_state = frappe.cache().get_value(key)
			if cached_state is not None:
				return bool(cached_state)

		self.authenticate()
		return True

	def clear_session(self):
		frappe.cache().delete_value(self._cache_key())

	def _mark_validated(self):
		frappe.cache().set_value(self._cache_key(), 1, expires_in_sec=SESSION_VALIDATION_TTL)

	def _cache_key(self):
		# Keyed on the settings timestamp so any credential edit invalidates it.
		return cache_key("auth", self.auth_type, self.settings.modified or "new")

	# -- helpers ---------------------------------------------------------
	@staticmethod
	def sanitize_user(user: dict) -> dict:
		"""Strip anything sensitive before a Traccar user reaches the client."""
		if not isinstance(user, dict):
			return {}
		blocked = {"password", "token", "attributes"}
		return {k: v for k, v in user.items() if k not in blocked}
