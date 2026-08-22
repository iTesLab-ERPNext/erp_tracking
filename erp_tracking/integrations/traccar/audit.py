"""Audit feature module (Section 33).

GET /audit's spec description says "Admin only" explicitly - not just a
UI convention, this reflects how Traccar itself scopes the endpoint. Kept
Manager-only in api.py to match. No security override in the spec beyond
the global default, so this goes through the normal authenticated path.
"""

from __future__ import annotations

from .client import TraccarClient
from .utils import to_iso8601


def get_audit_log(from_date, to_date) -> dict:
	if not from_date or not to_date:
		return {
			"success": False,
			"data": None,
			"message": "Both From and To dates are required.",
			"status_code": 400,
			"error": "TraccarClientValidationError",
		}

	params = {"from": to_iso8601(from_date), "to": to_iso8601(to_date)}
	return TraccarClient().request_safe("GET", "audit", params=params)
