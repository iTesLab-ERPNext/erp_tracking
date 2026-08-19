"""Top-level whitelisted API surface for erp_tracking.

Phase 1 only exposes connection status, used by the Dashboard's 🟢/🔴
Connected indicator (Section 36). Feature-specific whitelisted methods
(get_devices, get_positions, generate_report, send_command, ...) are added
here in their respective phases, but each delegates to its own
integrations/traccar/<feature>.py module rather than talking to
TraccarClient directly - this file stays a thin router, never business logic.
"""

from __future__ import annotations

import frappe

from erp_tracking.integrations.traccar import dashboard as dashboard_module
from erp_tracking.integrations.traccar import devices as devices_module
from erp_tracking.integrations.traccar import groups as groups_module
from erp_tracking.integrations.traccar import users as users_module
from erp_tracking.integrations.traccar.config import get_settings
from erp_tracking.integrations.traccar.exceptions import TraccarConfigurationError
from erp_tracking.integrations.traccar.permissions import require_read


@frappe.whitelist()
def get_connection_status():
	"""Lightweight, read-only status check for dashboard widgets.

	Does NOT make a network call - it reports the last cached result from
	Traccar Settings (populated by the Test Connection button). This keeps
	dashboard loads fast; use test_connection() for an active check.
	"""
	settings_doc = frappe.get_single("Traccar Settings")

	try:
		get_settings()
		configured = True
	except TraccarConfigurationError:
		configured = False

	return {
		"configured": configured,
		"enabled": bool(settings_doc.enabled),
		"connection_status": settings_doc.connection_status or "Not Tested",
		"last_connection_test": settings_doc.last_connection_test,
	}


# -----------------------------------------------------------------------------
# Dashboard (Section 36)
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_dashboard_summary():
	require_read()
	return dashboard_module.get_dashboard_summary()


# -----------------------------------------------------------------------------
# Devices (Section 10-11)
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_devices(keyword: str | None = None, limit: int | None = None, offset: int | None = None, refresh: bool = False):
	require_read()
	return devices_module.get_devices(
		keyword=keyword,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_device(device_id: int):
	require_read()
	return devices_module.get_device(frappe.utils.cint(device_id))


# -----------------------------------------------------------------------------
# Groups (Section 12)
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_groups(keyword: str | None = None, limit: int | None = None, offset: int | None = None, refresh: bool = False):
	require_read()
	return groups_module.get_groups(
		keyword=keyword,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_group(group_id: int):
	require_read()
	return groups_module.get_group(frappe.utils.cint(group_id))


@frappe.whitelist()
def get_devices_in_group(group_id: int):
	require_read()
	return groups_module.devices_in_group(frappe.utils.cint(group_id))


# -----------------------------------------------------------------------------
# Users (Section 13)
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_users(keyword: str | None = None, limit: int | None = None, offset: int | None = None, refresh: bool = False):
	require_read()
	return users_module.get_users(
		keyword=keyword,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_user(user_id: int):
	require_read()
	return users_module.get_user(frappe.utils.cint(user_id))
