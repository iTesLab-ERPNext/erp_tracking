"""Centralized authentication for the Traccar integration.

Every other module (client.py, and every feature module built on top of it
in later phases) gets its auth headers from TraccarAuth. Nothing else is
allowed to build a Basic Auth header or an Authorization header itself -
that keeps the "one place secrets touch HTTP" guarantee from Section 41.
"""

from __future__ import annotations

import base64

from .config import TraccarSettingsData, get_settings
from .exceptions import TraccarConfigurationError


class TraccarAuth:
	"""Resolves Traccar Settings into request-ready auth headers.

	Supports both auth schemes defined in the OpenAPI spec's
	securitySchemes: BasicAuth (http/basic) and ApiKey (http/bearer).
	"""

	def __init__(self, settings: TraccarSettingsData | None = None):
		self._settings = settings

	@property
	def settings(self) -> TraccarSettingsData:
		if self._settings is None:
			self._settings = get_settings()
		return self._settings

	def authenticate(self) -> TraccarSettingsData:
		"""Validate that settings are complete enough to attempt a request.

		Does not itself make an HTTP call - client.py does that. This only
		checks local configuration, so bad config fails fast with a clear
		TraccarConfigurationError instead of a confusing network error.
		"""
		settings = self.settings

		if not settings.url:
			raise TraccarConfigurationError("Traccar server URL is not configured.")

		if not settings.enabled:
			raise TraccarConfigurationError("Traccar integration is disabled.")

		if settings.auth_type == "Basic Auth":
			if not settings.username or not settings.password:
				raise TraccarConfigurationError(
					"Basic Auth username/password are not configured."
				)
		elif settings.auth_type == "API Key":
			if not settings.api_key:
				raise TraccarConfigurationError("API Key is not configured.")
		else:
			raise TraccarConfigurationError(
				f"Unsupported authentication type: {settings.auth_type}"
			)

		return settings

	def get_auth_headers(self) -> dict:
		"""Build the Authorization header for the configured auth type.

		BasicAuth -> "Authorization: Basic <base64(user:pass)>"
		ApiKey    -> "Authorization: Bearer <token>"  (per securitySchemes.ApiKey: http/bearer)
		"""
		settings = self.authenticate()

		if settings.auth_type == "Basic Auth":
			token = base64.b64encode(
				f"{settings.username}:{settings.password}".encode("utf-8")
			).decode("ascii")
			return {"Authorization": f"Basic {token}"}

		if settings.auth_type == "API Key":
			return {"Authorization": f"Bearer {settings.api_key}"}

		# Unreachable: authenticate() already rejects unknown auth types.
		raise TraccarConfigurationError(
			f"Unsupported authentication type: {settings.auth_type}"
		)

	def validate_session(self) -> bool:
		"""Local-only check that current settings look usable.

		Real server-side validation happens via TraccarClient.get('server')
		against GET /session or GET /server (see client.test_connection).
		This method exists so callers can cheaply check "is auth even
		configured" before firing a network request.
		"""
		try:
			self.authenticate()
			return True
		except TraccarConfigurationError:
			return False

	def clear_session(self):
		"""Drop any cached settings so the next call re-reads from the DB.

		Called after Traccar Settings is saved, so a changed password/API
		key takes effect immediately without a bench restart.
		"""
		self._settings = None
