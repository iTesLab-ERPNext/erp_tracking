"""Centralized role checks for whitelisted Traccar API methods (Section 40).

Every whitelisted method in the app calls one of these instead of rolling
its own frappe.only_for(...) list, so the Manager/User/Viewer matrix stays
consistent as new features are added in later phases.
"""

from __future__ import annotations

import frappe

MANAGER = "ERP Tracking Manager"
USER = "ERP Tracking User"
VIEWER = "ERP Tracking Viewer"

#: Roles allowed to read fleet data (devices, groups, users, positions,
#: reports, events, geofences) - i.e. anyone with any ERP Tracking role,
#: plus System Manager for administrators managing the site itself.
READ_ROLES = ("System Manager", MANAGER, USER, VIEWER)

#: Roles allowed to change things (create/update/delete on Traccar-backed
#: resources) - Viewers are read-only by design (Section 40).
WRITE_ROLES = ("System Manager", MANAGER, USER)

#: Roles allowed to send commands, view audit logs, or touch settings -
#: Manager only (Sections 25, 33, 40, 41).
ADMIN_ROLES = ("System Manager", MANAGER)


def require_read():
	frappe.only_for(READ_ROLES)


def require_write():
	frappe.only_for(WRITE_ROLES)


def require_admin():
	frappe.only_for(ADMIN_ROLES)
