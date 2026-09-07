"""Create ERP Tracking roles on existing sites."""

from erp_tracking.install import create_tracking_roles


def execute():
	create_tracking_roles()
