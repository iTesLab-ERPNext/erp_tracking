"""Installation routines for erp_tracking.

Creates the three roles used throughout the app (Section 40 of the spec):

- ERP Tracking Manager : full access, settings, connection test, commands, audit
- ERP Tracking User     : devices, positions, reports, events, geofences, export
- ERP Tracking Viewer   : read-only access

Role -> DocType permission wiring for each DocType is added incrementally as
those DocTypes are built in later phases (Devices, Reports, Commands, etc.).
This keeps permissions defined next to the DocType that owns them instead of
being duplicated here.
"""

import frappe

ROLES = [
	"ERP Tracking Manager",
	"ERP Tracking User",
	"ERP Tracking Viewer",
]


def after_install():
	create_roles()
	create_traccar_settings_permissions()
	frappe.db.commit()


def create_roles():
	for role_name in ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = 1
		role.insert(ignore_permissions=True)


def create_traccar_settings_permissions():
	"""Traccar Settings holds credentials, so only Manager may read/write it.
	Users and Viewers never get a permission row here (Section 41: settings
	and credentials must be restricted).
	"""
	if not frappe.db.exists("DocType", "Traccar Settings"):
		return

	doctype = frappe.get_doc("DocType", "Traccar Settings")
	existing_roles = {p.role for p in doctype.permissions}

	if "ERP Tracking Manager" not in existing_roles:
		doctype.append(
			"permissions",
			{
				"role": "ERP Tracking Manager",
				"read": 1,
				"write": 1,
				"create": 1,
				"delete": 0,
				"print": 0,
				"email": 0,
				"export": 0,
				"share": 0,
			},
		)
		doctype.save(ignore_permissions=True)
