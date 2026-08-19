"""Exception hierarchy for the Traccar integration.

Every exception carries a `status_code` (HTTP status where applicable, or
None for local/config errors) and a `message` that is safe to show directly
to end users in the Frappe Desk UI - no stack traces, no leaked internals.
"""


class TraccarError(Exception):
	"""Base class for all Traccar integration errors."""

	def __init__(self, message: str, status_code: int | None = None):
		self.message = message
		self.status_code = status_code
		super().__init__(message)


class TraccarConfigurationError(TraccarError):
	"""Raised when Traccar Settings is missing, disabled, or invalid."""


class TraccarConnectionError(TraccarError):
	"""Raised when the Traccar server cannot be reached (DNS, refused, etc.)."""


class TraccarTimeoutError(TraccarError):
	"""Raised when a request exceeds the configured timeout."""


class TraccarAuthenticationError(TraccarError):
	"""Raised on HTTP 401 / 403 responses from Traccar."""


class TraccarAPIError(TraccarError):
	"""Raised for any other non-2xx response from Traccar (404, 429, 5xx, ...)."""


# Maps HTTP status codes to a short, user-facing message.
# Used by client.py to build consistent, non-leaky error messages across
# every feature module (devices, positions, reports, commands, ...).
HTTP_STATUS_MESSAGES = {
	400: "Invalid request sent to Traccar.",
	401: "Authentication failed.",
	403: "You do not have permission to access this resource.",
	404: "The requested resource was not found on the Traccar server.",
	408: "Request timeout.",
	429: "Too many requests. Please slow down and try again shortly.",
	500: "Traccar server encountered an internal error.",
	502: "Traccar server is unavailable.",
	503: "Traccar server is unavailable.",
	504: "Traccar server did not respond in time.",
}


def status_message(status_code: int) -> str:
	return HTTP_STATUS_MESSAGES.get(status_code, "Traccar server unavailable.")
