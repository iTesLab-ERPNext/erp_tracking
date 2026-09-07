"""Installation and migration hooks for the ERP Tracking app."""

import frappe

from erp_tracking.permissions import ROLE_MANAGER, ROLE_USER, ROLE_VIEWER

TRACKING_ROLES = (ROLE_MANAGER, ROLE_USER, ROLE_VIEWER)


def after_install():
	create_tracking_roles()
	ensure_settings_singleton()


def after_migrate():
	create_tracking_roles()


def create_tracking_roles():
	"""Create the three ERP Tracking roles if they do not exist yet."""
	for role_name in TRACKING_ROLES:
		if frappe.db.exists("Role", role_name):
			continue

		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = 1
		role.is_custom = 0
		role.insert(ignore_permissions=True)

	frappe.db.commit()


def ensure_settings_singleton():
	"""Materialise the Traccar Settings single doc with safe defaults."""
	settings = frappe.get_single("Traccar Settings")
	if not settings.timeout:
		settings.timeout = 30
	if settings.verify_ssl is None:
		settings.verify_ssl = 1
	if not settings.auth_type:
		settings.auth_type = "Basic Auth"
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)
	frappe.db.commit()
