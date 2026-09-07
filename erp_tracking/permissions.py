"""Central permission helpers for ERP Tracking.

Every whitelisted method in :mod:`erp_tracking.api` funnels through one of the
``ensure_*`` helpers below.  Roles are never checked ad-hoc inside the
integration layer so that the policy stays in a single, auditable place.
"""

import frappe
from frappe import _

ROLE_MANAGER = "ERP Tracking Manager"
ROLE_USER = "ERP Tracking User"
ROLE_VIEWER = "ERP Tracking Viewer"

SYSTEM_ROLES = ("System Manager", "Administrator")

READ_ROLES = (ROLE_MANAGER, ROLE_USER, ROLE_VIEWER) + SYSTEM_ROLES
WRITE_ROLES = (ROLE_MANAGER,) + SYSTEM_ROLES
COMMAND_ROLES = (ROLE_MANAGER,) + SYSTEM_ROLES
ADMIN_ROLES = (ROLE_MANAGER,) + SYSTEM_ROLES


def _roles() -> set:
	return set(frappe.get_roles(frappe.session.user))


def has_any_role(roles) -> bool:
	if frappe.session.user == "Administrator":
		return True
	return bool(_roles().intersection(roles))


def _throw(message):
	frappe.throw(message, frappe.PermissionError, title=_("Not permitted"))


def ensure_authenticated():
	if frappe.session.user in ("Guest", None, ""):
		frappe.throw(_("Please sign in to use ERP Tracking."), frappe.AuthenticationError)


def ensure_read():
	"""Any of the three tracking roles may read Traccar data."""
	ensure_authenticated()
	if not has_any_role(READ_ROLES):
		_throw(_("You do not have permission to access tracking data."))


def ensure_write():
	"""Creating/updating/deleting Traccar objects is manager-only."""
	ensure_authenticated()
	if not has_any_role(WRITE_ROLES):
		_throw(_("You do not have permission to modify tracking data."))


def ensure_command():
	"""Dispatching commands to hardware is manager-only."""
	ensure_authenticated()
	if not has_any_role(COMMAND_ROLES):
		_throw(_("You do not have permission to send commands to devices."))


def ensure_admin():
	"""Audit log, server administration and settings."""
	ensure_authenticated()
	if not has_any_role(ADMIN_ROLES):
		_throw(_("You do not have permission to access this resource."))


def is_manager() -> bool:
	return has_any_role(ADMIN_ROLES)


def is_viewer_only() -> bool:
	roles = _roles()
	return ROLE_VIEWER in roles and not roles.intersection((ROLE_MANAGER, ROLE_USER) + SYSTEM_ROLES)
