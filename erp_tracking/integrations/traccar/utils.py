"""Small shared helpers used by every Traccar feature module.

Kept deliberately tiny in Phase 1. Grows in later phases as devices.py,
reports.py, etc. need shared pagination/date helpers - defined once here
instead of duplicated per module (Section 38: reusable list engine).
"""

from __future__ import annotations

import frappe


def to_iso8601(value) -> str | None:
	"""Format a Frappe datetime value as the ISO 8601 string Traccar expects,
	e.g. 1963-11-22T18:30:00Z.
	"""
	if not value:
		return None
	dt = frappe.utils.get_datetime(value)
	return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def paginate_params(limit: int | None = None, offset: int | None = None) -> dict:
	"""Build the {limit, offset} query params Traccar's list endpoints accept,
	omitting keys that weren't provided instead of sending limit=None.
	"""
	params = {}
	if limit is not None:
		params["limit"] = int(limit)
	if offset is not None:
		params["offset"] = int(offset)
	return params
