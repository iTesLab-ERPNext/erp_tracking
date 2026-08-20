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

from erp_tracking.integrations.traccar import commands as commands_module
from erp_tracking.integrations.traccar import dashboard as dashboard_module
from erp_tracking.integrations.traccar import devices as devices_module
from erp_tracking.integrations.traccar import geofences as geofences_module
from erp_tracking.integrations.traccar import groups as groups_module
from erp_tracking.integrations.traccar import notifications as notifications_module
from erp_tracking.integrations.traccar import positions as positions_module
from erp_tracking.integrations.traccar import reports as reports_module
from erp_tracking.integrations.traccar import route as route_module
from erp_tracking.integrations.traccar import users as users_module
from erp_tracking.integrations.traccar.config import get_settings
from erp_tracking.integrations.traccar.exceptions import TraccarConfigurationError, TraccarError
from erp_tracking.integrations.traccar.permissions import require_admin, require_read, require_write


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


# -----------------------------------------------------------------------------
# Live Positions & Position History (Sections 14-15)
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_live_positions(device_id: int | None = None, refresh: bool = False):
	require_read()
	return positions_module.get_live_positions(
		device_id=frappe.utils.cint(device_id) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_position_history(device_id: int, from_date, to_date):
	require_read()
	return positions_module.get_position_history(
		device_id=frappe.utils.cint(device_id), from_date=from_date, to_date=to_date
	)


def _stream_download(content, filename: str, content_type: str):
	frappe.response["type"] = "download"
	frappe.response["filename"] = filename
	frappe.response["filecontent"] = content
	frappe.response.headers = frappe.response.headers or {}
	frappe.response.headers["Content-Type"] = content_type


@frappe.whitelist()
def download_positions_csv(device_id: int, from_date, to_date):
	"""GET-able download endpoint (Section 15/39: use Traccar's native CSV
	export rather than rebuilding it). Called via a direct URL, not frappe.call,
	so the browser triggers a real file download.
	"""
	require_read()
	try:
		content = positions_module.export_positions_csv(frappe.utils.cint(device_id), from_date, to_date)
	except TraccarError as exc:
		frappe.throw(exc.message)
	_stream_download(content, f"positions_{device_id}.csv", "text/csv")


@frappe.whitelist()
def download_positions_kml(device_id: int, from_date, to_date):
	require_read()
	try:
		content = positions_module.export_positions_kml(frappe.utils.cint(device_id), from_date, to_date)
	except TraccarError as exc:
		frappe.throw(exc.message)
	_stream_download(content, f"positions_{device_id}.kml", "application/vnd.google-earth.kml+xml")


@frappe.whitelist()
def download_positions_gpx(device_id: int, from_date, to_date):
	require_read()
	try:
		content = positions_module.export_positions_gpx(frappe.utils.cint(device_id), from_date, to_date)
	except TraccarError as exc:
		frappe.throw(exc.message)
	_stream_download(content, f"positions_{device_id}.gpx", "application/gpx+xml")


# -----------------------------------------------------------------------------
# Route (Section 19)
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_route(device_ids=None, group_ids=None, from_date=None, to_date=None):
	require_read()
	device_ids = frappe.parse_json(device_ids) if isinstance(device_ids, str) else device_ids
	group_ids = frappe.parse_json(group_ids) if isinstance(group_ids, str) else group_ids
	return route_module.get_route(device_ids=device_ids, group_ids=group_ids, from_date=from_date, to_date=to_date)


# -----------------------------------------------------------------------------
# Reports: Trips, Stops, Summary, Events (Sections 16-21, 37)
# -----------------------------------------------------------------------------
def _parse_list_arg(value):
	if isinstance(value, str):
		return frappe.parse_json(value)
	return value


@frappe.whitelist()
def get_report(report_key: str, device_ids=None, group_ids=None, from_date=None, to_date=None, event_types=None, daily=None):
	require_read()
	return reports_module.generate_report(
		report_key=report_key,
		device_ids=_parse_list_arg(device_ids),
		group_ids=_parse_list_arg(group_ids),
		from_date=from_date,
		to_date=to_date,
		event_types=_parse_list_arg(event_types),
		daily=frappe.utils.sbool(daily) if daily is not None else None,
	)


@frappe.whitelist()
def download_report(report_key: str, download_type: str, device_ids=None, group_ids=None, from_date=None, to_date=None, event_types=None, daily=None):
	"""GET-able endpoint: downloads the report as XLSX, or triggers a
	native email delivery when download_type == "mail" (Section 16-18/21).
	"""
	require_read()
	try:
		content = reports_module.download_report(
			report_key=report_key,
			download_type=download_type,
			device_ids=_parse_list_arg(device_ids),
			group_ids=_parse_list_arg(group_ids),
			from_date=from_date,
			to_date=to_date,
			event_types=_parse_list_arg(event_types),
			daily=frappe.utils.sbool(daily) if daily is not None else None,
		)
	except TraccarError as exc:
		frappe.throw(exc.message)

	if download_type == "mail":
		# 204 from Traccar - no file to stream, just confirm it was queued.
		frappe.response["type"] = "json"
		frappe.response["message"] = {"success": True, "message": "Report queued for email delivery."}
		return

	_stream_download(
		content,
		f"{report_key}_report.xlsx",
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	)


# -----------------------------------------------------------------------------
# Geofences (Section 22) - full CRUD, spec supports it
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_geofences(keyword=None, device_id=None, group_id=None, limit=None, offset=None, refresh=False):
	require_read()
	return geofences_module.get_geofences(
		keyword=keyword,
		device_id=frappe.utils.cint(device_id) or None,
		group_id=frappe.utils.cint(group_id) or None,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_geofence(geofence_id: int):
	require_read()
	return geofences_module.get_geofence(frappe.utils.cint(geofence_id))


@frappe.whitelist()
def create_geofence(name: str, area: str, description: str | None = None, calendar_id=None):
	require_write()
	return geofences_module.create_geofence(name=name, area=area, description=description, calendar_id=frappe.utils.cint(calendar_id) or None)


@frappe.whitelist()
def update_geofence(geofence_id: int, **fields):
	require_write()
	fields.pop("cmd", None)
	return geofences_module.update_geofence(frappe.utils.cint(geofence_id), **fields)


@frappe.whitelist()
def delete_geofence(geofence_id: int):
	require_write()
	return geofences_module.delete_geofence(frappe.utils.cint(geofence_id))


# -----------------------------------------------------------------------------
# Notifications (Section 23) - full CRUD, spec supports it. Manager-only:
# notification rules route real emails/SMS, so configuring them is treated
# as an administrative action, not a general "read" one (Section 40/41).
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_notifications(keyword=None, device_id=None, group_id=None, limit=None, offset=None, refresh=False):
	require_admin()
	return notifications_module.get_notifications(
		keyword=keyword,
		device_id=frappe.utils.cint(device_id) or None,
		group_id=frappe.utils.cint(group_id) or None,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_notification_types():
	require_admin()
	return notifications_module.get_notification_types()


@frappe.whitelist()
def get_notificators(announcement=None):
	require_admin()
	return notifications_module.get_notificators(announcement=frappe.utils.sbool(announcement) if announcement is not None else None)


@frappe.whitelist()
def create_notification(type_: str, notificators: str, description: str | None = None, always=False, calendar_id=None):
	require_admin()
	return notifications_module.create_notification(
		type_=type_,
		notificators=notificators,
		description=description,
		always=frappe.utils.sbool(always),
		calendar_id=frappe.utils.cint(calendar_id) or None,
	)


@frappe.whitelist()
def update_notification(notification_id: int, **fields):
	require_admin()
	fields.pop("cmd", None)
	return notifications_module.update_notification(frappe.utils.cint(notification_id), **fields)


@frappe.whitelist()
def delete_notification(notification_id: int):
	require_admin()
	return notifications_module.delete_notification(frappe.utils.cint(notification_id))


@frappe.whitelist()
def send_test_notification():
	require_admin()
	return notifications_module.send_test_notification()


# -----------------------------------------------------------------------------
# Commands (Sections 24-26) - Manager-only throughout. Section 25: "Never
# allow unauthorized users to send commands. Implement strict permission
# checking." Section 40 lists Commands only under the Manager role.
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_commands(keyword=None, device_id=None, group_id=None, limit=None, offset=None, refresh=False):
	require_admin()
	return commands_module.get_commands(
		keyword=keyword,
		device_id=frappe.utils.cint(device_id) or None,
		group_id=frappe.utils.cint(group_id) or None,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_command(command_id: int):
	require_admin()
	return commands_module.get_command(frappe.utils.cint(command_id))


@frappe.whitelist()
def get_command_types(device_id=None, text_channel=None):
	require_admin()
	return commands_module.get_command_types(
		device_id=frappe.utils.cint(device_id) or None,
		text_channel=frappe.utils.sbool(text_channel) if text_channel is not None else None,
	)


@frappe.whitelist()
def get_available_commands_for_device(device_id: int):
	require_admin()
	return commands_module.get_available_commands_for_device(frappe.utils.cint(device_id))


@frappe.whitelist()
def create_saved_command(device_id=None, description: str = "", type_: str = "", text_channel=False, attributes=None):
	require_admin()
	return commands_module.create_saved_command(
		device_id=frappe.utils.cint(device_id) or None,
		description=description,
		type_=type_,
		text_channel=frappe.utils.sbool(text_channel),
		attributes=_parse_list_arg(attributes),
	)


@frappe.whitelist()
def update_saved_command(command_id: int, **fields):
	require_admin()
	fields.pop("cmd", None)
	return commands_module.update_saved_command(frappe.utils.cint(command_id), **fields)


@frappe.whitelist()
def delete_saved_command(command_id: int):
	require_admin()
	return commands_module.delete_saved_command(frappe.utils.cint(command_id))


@frappe.whitelist()
def send_command(device_id=None, group_id=None, saved_command_id=None, type_=None, text_channel=False, attributes=None):
	require_admin()
	result = commands_module.send_command(
		device_id=frappe.utils.cint(device_id) or None,
		group_id=frappe.utils.cint(group_id) or None,
		saved_command_id=frappe.utils.cint(saved_command_id) or None,
		type_=type_ or None,
		text_channel=frappe.utils.sbool(text_channel),
		attributes=_parse_list_arg(attributes),
	)
	if result["success"]:
		frappe.get_doc(
			{
				"doctype": "Traccar Command Log",
				"user": frappe.session.user,
				"device_id": device_id,
				"group_id": group_id,
				"command_type": type_,
				"status": "Sent" if result["status_code"] == 200 else "Queued",
				"timestamp": frappe.utils.now_datetime(),
			}
		).insert(ignore_permissions=True)
	return result
