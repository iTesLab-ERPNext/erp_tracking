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

from erp_tracking.integrations.traccar import audit as audit_module
from erp_tracking.integrations.traccar import calendars as calendars_module
from erp_tracking.integrations.traccar import commands as commands_module
from erp_tracking.integrations.traccar import dashboard as dashboard_module
from erp_tracking.integrations.traccar import devices as devices_module
from erp_tracking.integrations.traccar import drivers as drivers_module
from erp_tracking.integrations.traccar import geofences as geofences_module
from erp_tracking.integrations.traccar import groups as groups_module
from erp_tracking.integrations.traccar import maintenance as maintenance_module
from erp_tracking.integrations.traccar import notifications as notifications_module
from erp_tracking.integrations.traccar import orders as orders_module
from erp_tracking.integrations.traccar import positions as positions_module
from erp_tracking.integrations.traccar import reports as reports_module
from erp_tracking.integrations.traccar import route as route_module
from erp_tracking.integrations.traccar import server as server_module
from erp_tracking.integrations.traccar import statistics as statistics_module
from erp_tracking.integrations.traccar import stream as stream_module
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


# -----------------------------------------------------------------------------
# Drivers (Section 27) - full CRUD, spec supports it. Same read/write split
# as Devices/Groups (all three roles read, Viewer excluded from writes).
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_drivers(keyword=None, device_id=None, group_id=None, limit=None, offset=None, refresh=False):
	require_read()
	return drivers_module.get_drivers(
		keyword=keyword,
		device_id=frappe.utils.cint(device_id) or None,
		group_id=frappe.utils.cint(group_id) or None,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_driver(driver_id: int):
	require_read()
	return drivers_module.get_driver(frappe.utils.cint(driver_id))


@frappe.whitelist()
def create_driver(name: str, unique_id: str, attributes=None):
	require_write()
	return drivers_module.create_driver(name=name, unique_id=unique_id, attributes=_parse_list_arg(attributes))


@frappe.whitelist()
def update_driver(driver_id: int, **fields):
	require_write()
	fields.pop("cmd", None)
	return drivers_module.update_driver(frappe.utils.cint(driver_id), **fields)


@frappe.whitelist()
def delete_driver(driver_id: int):
	require_write()
	return drivers_module.delete_driver(frappe.utils.cint(driver_id))


# -----------------------------------------------------------------------------
# Maintenance (Section 28) - full CRUD, spec supports it
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_maintenance_items(keyword=None, device_id=None, group_id=None, limit=None, offset=None, refresh=False):
	require_read()
	return maintenance_module.get_maintenance_items(
		keyword=keyword,
		device_id=frappe.utils.cint(device_id) or None,
		group_id=frappe.utils.cint(group_id) or None,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_maintenance_item(maintenance_id: int):
	require_read()
	return maintenance_module.get_maintenance_item(frappe.utils.cint(maintenance_id))


@frappe.whitelist()
def create_maintenance_item(name: str, type_: str, start, period, attributes=None):
	require_write()
	return maintenance_module.create_maintenance_item(
		name=name, type_=type_, start=frappe.utils.flt(start), period=frappe.utils.flt(period), attributes=_parse_list_arg(attributes)
	)


@frappe.whitelist()
def update_maintenance_item(maintenance_id: int, **fields):
	require_write()
	fields.pop("cmd", None)
	return maintenance_module.update_maintenance_item(frappe.utils.cint(maintenance_id), **fields)


@frappe.whitelist()
def delete_maintenance_item(maintenance_id: int):
	require_write()
	return maintenance_module.delete_maintenance_item(frappe.utils.cint(maintenance_id))


# -----------------------------------------------------------------------------
# Calendars (Section 29) - full CRUD, Manager-only (see calendars.py docstring)
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_calendars(keyword=None, limit=None, offset=None, refresh=False):
	require_admin()
	return calendars_module.get_calendars(
		keyword=keyword,
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_calendar(calendar_id: int):
	require_admin()
	return calendars_module.get_calendar(frappe.utils.cint(calendar_id))


@frappe.whitelist()
def create_calendar(name: str, ical_data: str, attributes=None):
	require_admin()
	return calendars_module.create_calendar(name=name, ical_data=ical_data, attributes=_parse_list_arg(attributes))


@frappe.whitelist()
def update_calendar(calendar_id: int, name=None, ical_data=None, attributes=None):
	require_admin()
	return calendars_module.update_calendar(
		frappe.utils.cint(calendar_id), name=name, ical_data=ical_data, attributes=_parse_list_arg(attributes)
	)


@frappe.whitelist()
def delete_calendar(calendar_id: int):
	require_admin()
	return calendars_module.delete_calendar(frappe.utils.cint(calendar_id))


# -----------------------------------------------------------------------------
# Server Information (Section 30) - GET is public per the spec (see
# server.py), but still routed through a whitelisted method rather than
# exposed directly, so the same standardized response/error shape applies
# and the Desk page doesn't need special-case handling for one endpoint.
# Read is available to all three roles (server version/map defaults are not
# sensitive); update is Manager-only.
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_server_info():
	require_read()
	return server_module.get_server_info()


@frappe.whitelist()
def update_server_info(**fields):
	require_admin()
	fields.pop("cmd", None)
	return server_module.update_server_info(**fields)


@frappe.whitelist()
def get_server_geocode(latitude: float, longitude: float):
	require_read()
	return server_module.get_geocode(latitude, longitude)


@frappe.whitelist()
def get_server_timezones():
	require_read()
	return server_module.get_timezones()


# -----------------------------------------------------------------------------
# Server Health (Section 31) - GET /health is public per the spec.
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_health():
	require_read()
	return server_module.get_health()


# -----------------------------------------------------------------------------
# Server Statistics (Section 32) - Manager-only, matches Section 40's
# System/Administration grouping.
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_statistics(from_date, to_date):
	require_admin()
	return statistics_module.get_statistics(from_date=from_date, to_date=to_date)


# -----------------------------------------------------------------------------
# Audit Logs (Section 33) - Manager-only; the spec's own description says
# "Admin only" for GET /audit.
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_audit_log(from_date, to_date):
	require_admin()
	return audit_module.get_audit_log(from_date=from_date, to_date=to_date)


# -----------------------------------------------------------------------------
# Orders (Section 34) - full CRUD, same read/write split as Drivers/Geofences
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_orders(keyword=None, user_id=None, exclude_attributes=False, limit=None, offset=None, refresh=False):
	require_read()
	return orders_module.get_orders(
		keyword=keyword,
		user_id=frappe.utils.cint(user_id) or None,
		exclude_attributes=frappe.utils.sbool(exclude_attributes),
		limit=frappe.utils.cint(limit) or None,
		offset=frappe.utils.cint(offset) or None,
		refresh=frappe.utils.sbool(refresh),
	)


@frappe.whitelist()
def get_order(order_id: int):
	require_read()
	return orders_module.get_order(frappe.utils.cint(order_id))


@frappe.whitelist()
def create_order(unique_id: str, description=None, from_address=None, to_address=None, attributes=None):
	require_write()
	return orders_module.create_order(
		unique_id=unique_id,
		description=description,
		from_address=from_address,
		to_address=to_address,
		attributes=_parse_list_arg(attributes),
	)


@frappe.whitelist()
def update_order(order_id: int, **fields):
	require_write()
	fields.pop("cmd", None)
	return orders_module.update_order(frappe.utils.cint(order_id), **fields)


@frappe.whitelist()
def delete_order(order_id: int):
	require_write()
	return orders_module.delete_order(frappe.utils.cint(order_id))


# -----------------------------------------------------------------------------
# Live Video (Section 35) - proxied deliberately; see stream.py docstring
# for why (Section 35 "don't proxy" vs Section 41 "never expose tokens").
# Read access only - same role split as Live Positions/Route.
# -----------------------------------------------------------------------------
@frappe.whitelist()
def get_stream_playlist(device_id: int, channel: int = 0):
	require_read()
	try:
		playlist = stream_module.get_playlist(frappe.utils.cint(device_id), frappe.utils.cint(channel))
	except TraccarError as exc:
		frappe.throw(exc.message)
	_stream_download(playlist, "live.m3u8", "application/vnd.apple.mpegurl")


@frappe.whitelist()
def get_stream_segment(device_id: int, channel: int = 0, index: int = 0):
	require_read()
	try:
		content = stream_module.get_segment(frappe.utils.cint(device_id), frappe.utils.cint(channel), frappe.utils.cint(index))
	except TraccarError as exc:
		frappe.throw(exc.message)
	_stream_download(content, f"{index}.ts", "video/mp2t")
