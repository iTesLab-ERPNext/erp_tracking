"""Shared helpers: response envelope, validation, caching, formatting."""

import functools
import json
import re
from datetime import datetime, timedelta, timezone

import frappe
from frappe import _
from frappe.utils import cint, cstr, get_datetime, now_datetime

from erp_tracking.integrations.traccar.exceptions import TraccarAPIError, TraccarError

SECRET_KEYS = {"password", "api_key", "apikey", "token", "authorization", "cookie", "secret"}
PATH_PATTERN = re.compile(r"^/[A-Za-z0-9/._~-]*$")
CACHE_PREFIX = "erp_tracking"


# ---------------------------------------------------------------------------
# Standard response envelope
# ---------------------------------------------------------------------------
def ok(data=None, message="", status_code=200):
	return {
		"success": True,
		"data": data,
		"message": message,
		"status_code": status_code,
		"error": None,
	}


def fail(message, status_code=400, error="TraccarAPIError"):
	return {
		"success": False,
		"data": None,
		"message": message,
		"status_code": status_code,
		"error": error,
	}


def standard_response(fn):
	"""Wrap a function so it always returns the standard envelope.

	The undecorated function stays reachable as ``fn.raw`` for internal callers
	that need the plain payload (the dashboard aggregator, exports, ...).
	"""

	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			result = fn(*args, **kwargs)
		except TraccarError as exc:
			log_traccar_error(fn.__name__, exc)
			return exc.as_dict()
		except frappe.PermissionError:
			raise
		except Exception as exc:  # noqa: BLE001 - converted to a safe envelope
			frappe.log_error(
				title=f"ERP Tracking: {fn.__name__}",
				message=frappe.get_traceback(with_context=True),
			)
			return fail(_("Unexpected error while contacting Traccar."), 500, type(exc).__name__)

		if isinstance(result, dict) and "success" in result and "status_code" in result:
			return result
		return ok(result)

	wrapper.raw = fn
	return wrapper


def log_traccar_error(context, exc: TraccarError):
	logger = frappe.logger("erp_tracking", allow_site=True)
	logger.warning(
		{
			"context": context,
			"error": type(exc).__name__,
			"status_code": exc.status_code,
			"detail": redact(exc.detail),
		}
	)


# ---------------------------------------------------------------------------
# Redaction / logging safety
# ---------------------------------------------------------------------------
def redact(value):
	"""Remove anything that looks like a credential before logging."""
	if value is None:
		return None
	if isinstance(value, dict):
		return {k: ("***" if k.lower() in SECRET_KEYS else redact(v)) for k, v in value.items()}
	if isinstance(value, (list, tuple)):
		return [redact(v) for v in value]

	text = cstr(value)
	text = re.sub(r"(?i)(bearer|basic)\s+[A-Za-z0-9._\-=+/]+", r"\1 ***", text)
	text = re.sub(r"(?i)(password|api_key|apikey|token)=[^&\s]+", r"\1=***", text)
	return text[:500]


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_path(path: str) -> str:
	"""Reject anything that is not a relative Traccar path.

	This is what stops a crafted frontend payload from turning the server-side
	client into an open HTTP proxy.
	"""
	path = cstr(path).strip()
	if not path.startswith("/") or "://" in path or ".." in path:
		raise TraccarAPIError(_("Invalid Traccar endpoint."), 400, detail=path)
	if not PATH_PATTERN.match(path):
		raise TraccarAPIError(_("Invalid Traccar endpoint."), 400, detail=path)
	return path


def to_iso(value, end_of_day=False):
	"""Convert a Frappe/ISO datetime into the ``1963-11-22T18:30:00Z`` form."""
	if not value:
		return None
	if isinstance(value, str) and value.endswith("Z") and "T" in value:
		return value

	dt = get_datetime(value)
	if dt is None:
		raise TraccarAPIError(_("Invalid date value."), 400)
	if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and end_of_day:
		dt = dt + timedelta(hours=23, minutes=59, seconds=59)
	if dt.tzinfo is None:
		dt = dt.replace(tzinfo=timezone.utc)
	return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_id_list(value):
	"""Accept 5, "5", "5,6", [5, 6] or '["5","6"]' and return [5, 6]."""
	if value in (None, "", [], "[]"):
		return []
	if isinstance(value, (int, float)):
		return [int(value)]
	if isinstance(value, str):
		value = value.strip()
		if value.startswith("["):
			try:
				value = json.loads(value)
			except ValueError:
				raise TraccarAPIError(_("Invalid identifier list."), 400)
		else:
			value = [part for part in value.split(",") if part.strip()]

	out = []
	for item in value or []:
		try:
			out.append(int(item))
		except (TypeError, ValueError):
			raise TraccarAPIError(_("Invalid identifier list."), 400)
	return out


def parse_str_list(value):
	if value in (None, "", [], "[]"):
		return []
	if isinstance(value, str):
		value = value.strip()
		if value.startswith("["):
			try:
				value = json.loads(value)
			except ValueError:
				return [value]
		else:
			value = [part.strip() for part in value.split(",") if part.strip()]
	return [cstr(item) for item in value or []]


def parse_bool(value):
	if value in (None, ""):
		return None
	if isinstance(value, bool):
		return value
	return cstr(value).lower() in ("1", "true", "yes", "on")


def parse_json_arg(value, default=None):
	if value in (None, ""):
		return default if default is not None else {}
	if isinstance(value, (dict, list)):
		return value
	try:
		return json.loads(value)
	except ValueError:
		raise TraccarAPIError(_("Invalid JSON payload."), 400)


def require(value, label):
	if value in (None, "", [], {}):
		raise TraccarAPIError(_("{0} is required.").format(_(label)), 400)
	return value


# ---------------------------------------------------------------------------
# Paging (used where Traccar has no limit/offset, e.g. positions and reports)
# ---------------------------------------------------------------------------
def paginate(rows, limit=None, offset=0):
	rows = rows or []
	total = len(rows)
	offset = max(cint(offset), 0)
	limit = cint(limit)
	if limit > 0:
		rows = rows[offset : offset + limit]
	elif offset:
		rows = rows[offset:]
	return {"items": rows, "total": total, "limit": limit, "offset": offset}


def sort_rows(rows, sort_by=None, sort_order="asc"):
	if not sort_by or not rows:
		return rows
	reverse = cstr(sort_order).lower() == "desc"

	def key(row):
		value = row.get(sort_by)
		return (value is None, cstr(value) if not isinstance(value, (int, float)) else value)

	try:
		return sorted(rows, key=key, reverse=reverse)
	except TypeError:
		return rows


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def cache_key(*parts):
	return ":".join([CACHE_PREFIX, *[cstr(p) for p in parts]])


def cached(key_parts, ttl, builder, refresh=False):
	"""Cache non-sensitive Traccar payloads. Credentials are never cached."""
	ttl = cint(ttl)
	key = cache_key(*key_parts)
	cache = frappe.cache()

	if not refresh and ttl > 0:
		hit = cache.get_value(key)
		if hit is not None:
			return hit

	value = builder()
	if ttl > 0 and value is not None:
		cache.set_value(key, value, expires_in_sec=ttl)
	return value


def clear_cache():
	frappe.cache().delete_keys(CACHE_PREFIX)


# ---------------------------------------------------------------------------
# Domain formatting helpers
# ---------------------------------------------------------------------------
def wkt_shape(area: str) -> str:
	"""Derive a human readable geofence shape from its WKT area string."""
	if not area:
		return ""
	head = cstr(area).strip().split("(")[0].strip().upper()
	return {
		"CIRCLE": _("Circle"),
		"POLYGON": _("Polygon"),
		"LINESTRING": _("Corridor"),
	}.get(head, head.title())


def knots_to_kmh(speed):
	if speed in (None, ""):
		return None
	return round(float(speed) * 1.852, 2)


def stringify_attributes(rows, keys=("attributes",)):
	"""Flatten dict-valued columns so the desk datatable can render them."""
	for row in rows or []:
		for key in keys:
			value = row.get(key)
			if isinstance(value, (dict, list)):
				row[key] = json.dumps(value, separators=(",", ":"), default=str)
	return rows


def utc_now_iso():
	return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_window():
	"""Start/end of the current site day, as Traccar ISO strings."""
	now = now_datetime()
	start = now.replace(hour=0, minute=0, second=0, microsecond=0)
	return to_iso(start), to_iso(now)
