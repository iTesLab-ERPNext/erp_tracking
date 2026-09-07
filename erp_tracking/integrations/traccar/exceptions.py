"""Typed exceptions for the Traccar integration.

Every exception carries a *user_message* that is safe to display in the desk UI
and an optional *status_code*.  Stack traces and raw upstream bodies are never
placed in ``user_message``.
"""

from frappe import _


class TraccarError(Exception):
	"""Base class for all Traccar integration errors."""

	default_message = "Traccar request failed."
	status_code = None

	def __init__(self, message=None, status_code=None, detail=None):
		self.user_message = message or _(self.default_message)
		self.status_code = status_code if status_code is not None else self.status_code
		# ``detail`` is for the server log only. It is never returned to the client.
		self.detail = detail
		super().__init__(self.user_message)

	def as_dict(self):
		return {
			"success": False,
			"data": None,
			"message": self.user_message,
			"status_code": self.status_code,
			"error": self.__class__.__name__,
		}


class TraccarConfigurationError(TraccarError):
	default_message = "Traccar is not configured."
	status_code = 0


class TraccarConnectionError(TraccarError):
	default_message = "Traccar server unavailable."
	status_code = 503


class TraccarTimeoutError(TraccarError):
	default_message = "Request timeout."
	status_code = 408


class TraccarAuthenticationError(TraccarError):
	default_message = "Authentication failed."
	status_code = 401


class TraccarPermissionError(TraccarError):
	default_message = "You do not have permission to access this resource."
	status_code = 403


class TraccarNotFoundError(TraccarError):
	default_message = "The requested Traccar record was not found."
	status_code = 404


class TraccarRateLimitError(TraccarError):
	default_message = "Too many requests to the Traccar server. Please retry shortly."
	status_code = 429


class TraccarAPIError(TraccarError):
	default_message = "Traccar rejected the request."
	status_code = 400
