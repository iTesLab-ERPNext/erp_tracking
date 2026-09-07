"""Generic, allow-listed list engine shared by every collection page.

One implementation serves devices, groups, users, geofences, drivers,
maintenance, notifications, saved commands, calendars and orders.  Query
parameters are filtered against :data:`LIST_CONFIG` so the frontend can never
smuggle an undocumented parameter into a Traccar request.
"""

import base64
import re

import frappe
from frappe import _
from frappe.utils import cint, cstr

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import LIST_CONFIG
from erp_tracking.integrations.traccar.exceptions import TraccarAPIError
from erp_tracking.integrations.traccar.utils import (
	cached,
	parse_bool,
	sort_rows,
	standard_response,
	stringify_attributes,
	wkt_shape,
)

DEFAULT_PAGE_LENGTH = 20
MAX_PAGE_LENGTH = 500

# Resources whose payloads are safe and stable enough to cache briefly.
CACHEABLE = {"devices", "groups", "users", "calendars", "drivers"}


def get_config(resource):
	config = LIST_CONFIG.get(cstr(resource))
	if not config:
		raise TraccarAPIError(_("Unknown resource."), 400, detail=cstr(resource))
	return config


def build_params(config, filters):
	"""Keep only parameters the specification defines for this endpoint."""
	filters = filters or {}
	params = {}
	for key in config["params"]:
		if key not in filters:
			continue
		value = filters.get(key)
		if value in (None, "", []):
			continue
		if key in ("all", "refresh", "excludeAttributes"):
			params[key] = "true" if parse_bool(value) else None
		elif key in ("limit", "offset", "userId", "deviceId", "groupId", "id"):
			params[key] = cint(value)
		else:
			params[key] = cstr(value)
	return {k: v for k, v in params.items() if v not in (None, "")}


# ---------------------------------------------------------------------------
# Per-resource enrichment (never invents fields - only derives from the payload)
# ---------------------------------------------------------------------------
def _enrich_geofences(rows):
	for row in rows:
		row["shape"] = wkt_shape(row.get("area"))
	return rows


def _enrich_calendars(rows):
	for row in rows:
		row["summary"], row["timezone"] = _describe_icalendar(row.get("data"))
		row.pop("data", None)
	return rows


def _enrich_users(rows):
	"""Users may not leak credentials or arbitrary attributes to the desk."""
	safe = []
	for row in rows:
		row.pop("password", None)
		row.pop("attributes", None)
		safe.append(row)
	return safe


ENRICHERS = {
	"geofences": _enrich_geofences,
	"calendars": _enrich_calendars,
	"users": _enrich_users,
}


def _describe_icalendar(data):
	"""Summarise the base64 iCalendar blob Traccar stores on a Calendar."""
	if not data:
		return "", ""
	try:
		text = base64.b64decode(data).decode("utf-8", errors="ignore")
	except Exception:  # noqa: BLE001
		return "", ""

	timezone = ""
	tz_match = re.search(r"^TZID:(.+)$", text, re.MULTILINE)
	if tz_match:
		timezone = tz_match.group(1).strip()

	summaries = re.findall(r"^SUMMARY:(.+)$", text, re.MULTILINE)
	rules = re.findall(r"^RRULE:(.+)$", text, re.MULTILINE)
	parts = [s.strip() for s in summaries[:3]]
	if rules:
		parts.append(rules[0].strip())
	return " | ".join(parts), timezone


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def fetch_list(resource, filters=None, refresh=False):
	"""Return ``{items, columns, page_length, has_more}`` for a resource."""
	config = get_config(resource)
	filters = dict(filters or {})

	page_length = cint(filters.get("limit")) or DEFAULT_PAGE_LENGTH
	page_length = max(1, min(page_length, MAX_PAGE_LENGTH))
	filters["limit"] = page_length

	sort_by = filters.pop("sort_by", None)
	sort_order = filters.pop("sort_order", "asc")

	params = build_params(config, filters)

	def _call():
		return get_client().get(config["endpoint"], params) or []

	if resource in CACHEABLE:
		ttl = cint(frappe.get_cached_value("Traccar Settings", None, "cache_ttl")) or 0
		rows = cached(("list", resource, frappe.as_json(params)), ttl, _call, refresh=refresh)
	else:
		rows = _call()

	rows = list(rows or [])
	enricher = ENRICHERS.get(resource)
	if enricher:
		rows = enricher(rows)

	rows = stringify_attributes(rows)
	rows = sort_rows(rows, sort_by, sort_order)

	return {
		"items": rows,
		"columns": config["columns"],
		"label": config["label"],
		"page_length": page_length,
		"offset": cint(params.get("offset")),
		# Traccar list endpoints do not return a total count, so "has more" is
		# inferred from a full page.
		"has_more": len(rows) >= page_length,
	}


@standard_response
def get_list(resource, filters=None, refresh=False):
	return fetch_list(resource, filters=filters, refresh=refresh)


def fetch_all(resource, filters=None, hard_limit=5000):
	"""Page through a resource server-side (used by exports and the dashboard)."""
	config = get_config(resource)
	filters = dict(filters or {})
	page_length = min(MAX_PAGE_LENGTH, hard_limit)
	offset = 0
	collected = []
	client = get_client()

	while len(collected) < hard_limit:
		filters.update({"limit": page_length, "offset": offset})
		params = build_params(config, filters)
		rows = client.get(config["endpoint"], params) or []
		collected.extend(rows)
		if len(rows) < page_length:
			break
		offset += page_length

	enricher = ENRICHERS.get(resource)
	if enricher:
		collected = enricher(collected)
	return stringify_attributes(collected[:hard_limit])
