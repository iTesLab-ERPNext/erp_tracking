"""Statistics feature module (Section 32).

GET /statistics has no security override in the spec, so it requires the
normal BasicAuth/ApiKey auth. It's also gated Manager-only in api.py to
match Section 40's "System" nav grouping (Server Information/Statistics/
Health sit alongside Audit Logs under Administration/System, which
Section 40's role table only grants to Manager).
"""

from __future__ import annotations

from .client import TraccarClient
from .utils import to_iso8601


def get_statistics(from_date, to_date) -> dict:
	if not from_date or not to_date:
		return {
			"success": False,
			"data": None,
			"message": "Both From and To dates are required.",
			"status_code": 400,
			"error": "TraccarClientValidationError",
		}

	params = {"from": to_iso8601(from_date), "to": to_iso8601(to_date)}
	return TraccarClient().request_safe("GET", "statistics", params=params)
