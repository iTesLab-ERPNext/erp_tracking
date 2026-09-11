"""The whitelisted surface of ERP Tracking.

This is the only door between the desk and Traccar.  Every method:

1. checks the caller's role through :mod:`erp_tracking.permissions`;
2. validates and normalises its arguments;
3. delegates to the integration layer, which returns the standard envelope;
4. returns data that never contains credentials.
"""

import frappe
from frappe import _
from frappe.utils import cint, cstr, now_datetime

from erp_tracking import export as export_service
from erp_tracking.integrations.traccar import (
	audit,
	calendars,
	commands,
	devices,
	drivers,
	events,
	geofences,
	groups,
	listing,
	maintenance,
	notifications,
	orders,
	positions,
	reports,
	server,
	statistics,
	stream,
	users,
)
from erp_tracking.integrations.traccar.auth import TraccarAuth, get_settings
from erp_tracking.integrations.traccar.config import (
	AUDIT_COLUMNS,
	LIST_CONFIG,
	POSITION_COLUMNS,
	REPORT_CONFIG,
)
from erp_tracking.integrations.traccar.exceptions import TraccarError
from erp_tracking.integrations.traccar.utils import (
	clear_cache,
	fail,
	ok,
	parse_bool,
	parse_id_list,
	parse_json_arg,
	require,
	today_window,
)
from erp_tracking.permissions import (
	ROLE_MANAGER,
	ROLE_USER,
	ROLE_VIEWER,
	ensure_admin,
	ensure_command,
	ensure_read,
	ensure_write,
	is_manager,
)

# ---------------------------------------------------------------------------
# Connection and configuration
# ---------------------------------------------------------------------------


@frappe.whitelist()
def test_connection():
	"""Verify the stored credentials. Never returns a credential or a token."""
	ensure_admin()
	settings = get_settings()

	try:
		auth = TraccarAuth(settings)
		auth.clear_session()
		user = auth.authenticate()
		info = server.get_server_info.raw(refresh=True)
		_record_connection(settings, "Connected", None, info.get("version"))
		return {
			"success": True,
			"authenticated": True,
			"status_code": 200,
			"message": _("Connection successful"),
			"server_version": info.get("version"),
			"account": user.get("email") or user.get("name"),
		}
	except TraccarError as exc:
		_record_connection(settings, "Failed", exc.user_message, None)
		return {
			"success": False,
			"authenticated": False,
			"status_code": exc.status_code,
			"message": exc.user_message,
			"error": type(exc).__name__,
		}


def _record_connection(settings, status, error, version):
	frappe.db.set_value(
		"Traccar Settings",
		None,
		{
			"connection_status": status,
			"last_connection_test": now_datetime(),
			"last_error": cstr(error or "")[:500],
			"server_version": cstr(version or ""),
		},
		update_modified=False,
	)
	frappe.db.commit()
	frappe.clear_cache(doctype="Traccar Settings")


@frappe.whitelist()
def get_configuration_state():
	"""Everything the desk needs to render without ever seeing a secret."""
	ensure_read()
	settings = get_settings()
	return ok(
		{
			"enabled": bool(cint(settings.enabled)),
			"configured": bool(settings.traccar_url),
			"auth_type": settings.auth_type,
			"connection_status": settings.connection_status,
			"last_connection_test": cstr(settings.last_connection_test or ""),
			"server_version": settings.server_version,
			"live_video": bool(cint(settings.get("enable_live_video"))),
			"map_tile_url": settings.get("map_tile_url"),
			"map_attribution": settings.get("map_attribution"),
			"leaflet_js_url": settings.get("leaflet_js_url"),
			"leaflet_css_url": settings.get("leaflet_css_url"),
			"page_length": cint(settings.get("default_page_length")) or 20,
			"can_manage": is_manager(),
			"roles": {
				"manager": ROLE_MANAGER,
				"user": ROLE_USER,
				"viewer": ROLE_VIEWER,
			},
		}
	)


@frappe.whitelist()
def clear_tracking_cache():
	ensure_write()
	clear_cache()
	return ok(message=_("Cache cleared"))


def refresh_connection_status():
	"""Scheduled hourly probe so the dashboard badge stays meaningful."""
	settings = frappe.get_single("Traccar Settings")
	if not cint(settings.enabled) or not settings.traccar_url:
		return
	try:
		TraccarAuth(settings).validate_session(refresh=True)
		_record_connection(settings, "Connected", None, settings.server_version)
	except TraccarError as exc:
		_record_connection(settings, "Failed", exc.user_message, settings.server_version)


# ---------------------------------------------------------------------------
# Generic list engine
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_list(resource, filters=None, refresh=False):
	"""Backing call for every collection page."""
	ensure_read()
	if resource in ("users", "orders"):
		ensure_admin()
	return listing.get_list(resource, filters=parse_json_arg(filters, {}), refresh=parse_bool(refresh))


@frappe.whitelist()
def get_filter_options(include=None):
	"""Device / group / geofence choices used to build filter fields."""
	ensure_read()
	include = include or ["devices", "groups"]
	if isinstance(include, str):
		include = [part.strip() for part in include.split(",") if part.strip()]

	payload = {}
	try:
		if "devices" in include:
			payload["devices"] = devices.device_choices()
		if "groups" in include:
			payload["groups"] = groups.group_choices()
		if "geofences" in include:
			payload["geofences"] = geofences.geofence_choices()
		if "calendars" in include:
			payload["calendars"] = calendars.calendar_choices()
	except TraccarError as exc:
		return exc.as_dict()
	return ok(payload)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_dashboard(refresh=False):
	ensure_read()
	refresh = parse_bool(refresh)
	settings = get_settings()

	if not cint(settings.enabled) or not settings.traccar_url:
		return fail(_("Traccar is not configured."), 0, "TraccarConfigurationError")

	try:
		device_rows = listing.fetch_all("devices", {"excludeAttributes": True})
		group_rows = listing.fetch_all("groups")
		geofence_rows = listing.fetch_all("geofences")
		user_rows = listing.fetch_all("users") if is_manager() else []

		online = sum(1 for d in device_rows if cstr(d.get("status")) == "online")
		offline = sum(1 for d in device_rows if cstr(d.get("status")) == "offline")

		frm, to = today_window()
		device_ids = [cint(d.get("id")) for d in device_rows][:200]
		today_counts = {"events": 0, "trips": 0, "stops": 0}
		if device_ids:
			for key, report in (("events", "events"), ("trips", "trips"), ("stops", "stops")):
				try:
					rows = reports.fetch_report(
						report, {"deviceId": device_ids, "from": frm, "to": to, "type": ["%"]}
					)
					today_counts[key] = len(rows)
				except TraccarError:
					today_counts[key] = None

		return ok(
			{
				"connected": True,
				"cards": {
					"devices": len(device_rows),
					"online": online,
					"offline": offline,
					"groups": len(group_rows),
					"users": len(user_rows),
					"geofences": len(geofence_rows),
					"events_today": today_counts["events"],
					"trips_today": today_counts["trips"],
					"stops_today": today_counts["stops"],
				},
				"server_version": settings.server_version,
				"synced_at": cstr(now_datetime()),
			}
		)
	except TraccarError as exc:
		return exc.as_dict()


# ---------------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_devices(filters=None, refresh=False):
	ensure_read()
	return devices.list_devices(parse_json_arg(filters, {}), parse_bool(refresh))


@frappe.whitelist()
def get_device(device_id):
	ensure_read()
	return devices.get_device(device_id)


@frappe.whitelist()
def get_device_overview(device_id):
	"""Device detail header: the record plus its last known position."""
	ensure_read()
	try:
		device = devices.get_device.raw(device_id)
		latest = positions.fetch_latest(device_ids=[cint(device_id)])
		return ok({"device": device, "position": latest[0] if latest else None})
	except TraccarError as exc:
		return exc.as_dict()


@frappe.whitelist()
def update_device_accumulators(device_id, total_distance=None, hours=None):
	ensure_write()
	return devices.update_accumulators(device_id, total_distance, hours)


@frappe.whitelist()
def save_device(payload, device_id=None):
	"""Create or update a Device. The backend (``devices.py``) has carried
	full CRUD since it was first written; this is the whitelisted entry
	point that was missing.
	"""
	ensure_write()
	payload = parse_json_arg(payload, {})
	require(payload.get("name"), "Name")
	require(payload.get("uniqueId"), "Unique ID")
	if device_id:
		return devices.update_device(device_id, payload)
	return devices.create_device(payload)


@frappe.whitelist()
def delete_device(device_id):
	ensure_write()
	return devices.delete_device(device_id)


# ---------------------------------------------------------------------------
# Groups / users
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_group(group_id):
	ensure_read()
	return groups.get_group(group_id)


@frappe.whitelist()
def get_group_devices(group_id):
	ensure_read()
	return groups.get_group_devices(group_id)


@frappe.whitelist()
def save_group(payload, group_id=None):
	ensure_write()
	payload = parse_json_arg(payload, {})
	require(payload.get("name"), "Name")
	if group_id:
		return groups.update_group(group_id, payload)
	return groups.create_group(payload)


@frappe.whitelist()
def delete_group(group_id):
	ensure_write()
	return groups.delete_group(group_id)


@frappe.whitelist()
def get_users(filters=None, refresh=False):
	ensure_admin()
	return users.list_users(parse_json_arg(filters, {}), parse_bool(refresh))


@frappe.whitelist()
def get_user(user_id):
	ensure_admin()
	return users.get_user(user_id)


@frappe.whitelist()
def save_user(payload, user_id=None):
	"""Users are administered from inside ERPNext too, gated to managers
	only (same role check ``get_users`` already uses). The password is
	required on create and, on update, only sent on to Traccar when the
	caller actually supplied a new one - see ``users.update_user``.
	"""
	ensure_admin()
	payload = parse_json_arg(payload, {})
	require(payload.get("name"), "Name")
	require(payload.get("email"), "Email")
	if user_id:
		return users.update_user(user_id, payload)
	return users.create_user(payload)


@frappe.whitelist()
def delete_user(user_id):
	ensure_admin()
	return users.delete_user(user_id)


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_live_positions(device_ids=None, group_id=None, status=None, limit=None, offset=0, sort_by=None, sort_order="asc"):
	ensure_read()
	return positions.get_latest_positions(
		device_ids=device_ids,
		group_id=group_id,
		status=status,
		limit=limit,
		offset=offset,
		sort_by=sort_by,
		sort_order=sort_order,
	)


@frappe.whitelist()
def get_position_history(device_id, from_time, to_time, limit=None, offset=0, sort_by=None, sort_order="asc"):
	ensure_read()
	return positions.get_position_history(
		device_id, from_time, to_time, limit=limit, offset=offset, sort_by=sort_by, sort_order=sort_order
	)


@frappe.whitelist()
def export_positions(device_id, from_time, to_time, fmt="csv", geofence_id=None):
	"""CSV/GPX/KML come straight from Traccar; XLSX and PDF are rendered here."""
	ensure_read()
	fmt = cstr(fmt).lower()
	try:
		if fmt in ("csv", "gpx", "kml"):
			content, mime, extension = positions.download_positions(
				device_id, from_time, to_time, fmt, geofence_id
			)
		elif fmt in ("xlsx", "pdf"):
			rows = positions.fetch_history(device_id, from_time, to_time)
			content, mime, extension = export_service.build(
				rows,
				POSITION_COLUMNS,
				fmt,
				title=_("Position History"),
				meta_lines=[
					_("Device: {0}").format(device_id),
					_("Period: {0} to {1}").format(from_time, to_time),
				],
			)
		else:
			return fail(_("Unsupported export format."), 400)
	except TraccarError as exc:
		return exc.as_dict()

	export_service.send_download(
		content, export_service.build_filename("position-history", extension), mime
	)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_report_meta():
	ensure_read()
	return ok(
		{
			name: {
				"label": config["label"],
				"filters": config["filters"],
				"columns": config["columns"],
				"native_download": bool(config.get("download")),
			}
			for name, config in REPORT_CONFIG.items()
		}
	)


@frappe.whitelist()
def run_report(report, filters=None, limit=None, offset=0, sort_by=None, sort_order="asc"):
	ensure_read()
	return reports.run_report(
		cstr(report),
		parse_json_arg(filters, {}),
		limit=limit,
		offset=offset,
		sort_by=sort_by,
		sort_order=sort_order,
	)


@frappe.whitelist()
def export_report(report, filters=None, fmt="xlsx"):
	"""Export honours the page filters and prefers Traccar's native XLSX."""
	ensure_read()
	report = cstr(report)
	fmt = cstr(fmt).lower()
	filters = parse_json_arg(filters, {})

	try:
		config = reports.get_report_config(report)

		if fmt == "xlsx" and config.get("download"):
			content, mime = reports.download_native(report, filters, "xlsx")
			extension = "xlsx"
		else:
			rows = reports._decorate(report, reports.fetch_report(report, filters))
			content, mime, extension = export_service.build(
				rows,
				config["columns"],
				fmt,
				title=_(config["label"]),
				meta_lines=[
					_("Period: {0} to {1}").format(filters.get("from"), filters.get("to")),
				],
			)
	except TraccarError as exc:
		return exc.as_dict()

	export_service.send_download(
		content, export_service.build_filename(f"{report}-report", extension), mime
	)


@frappe.whitelist()
def mail_report(report, filters=None):
	"""Ask Traccar to deliver the report by e-mail (``type=mail``)."""
	ensure_read()
	return reports.mail_report(cstr(report), parse_json_arg(filters, {}))


@frappe.whitelist()
def get_combined_report(filters=None):
	"""``/reports/combined`` - route, events and positions for one request."""
	ensure_read()
	return reports.get_combined_report(parse_json_arg(filters, {}))


@frappe.whitelist()
def get_fleet_overview(from_time, to_time, device_ids=None, group_ids=None):
	"""KPIs, per-device/driver/group breakdowns and a trips-per-day series
	for the Reports > Overview tab - built from the existing trips/summary/
	events reports, not a new Traccar endpoint.
	"""
	ensure_read()
	return reports.get_fleet_overview(
		from_time,
		to_time,
		device_ids=parse_id_list(device_ids) or None,
		group_ids=parse_id_list(group_ids) or None,
	)


@frappe.whitelist()
def export_devices_report():
	"""``/reports/devices/{type}`` - Traccar's own fleet spreadsheet. This
	endpoint has no JSON variant, so unlike the other reports there is
	nothing to render in the desk table; it only ever downloads.
	"""
	ensure_read()
	try:
		content, mime = reports.fetch_devices_report()
	except TraccarError as exc:
		return exc.as_dict()
	export_service.send_download(content, export_service.build_filename("devices-report", "xlsx"), mime)


@frappe.whitelist()
def export_list(resource, filters=None, fmt="csv"):
	ensure_read()
	if resource in ("users", "orders"):
		ensure_admin()
	try:
		config = listing.get_config(resource)
		rows = listing.fetch_all(resource, parse_json_arg(filters, {}))
		content, mime, extension = export_service.build(
			rows, config["columns"], fmt, title=_(config["label"])
		)
	except TraccarError as exc:
		return exc.as_dict()

	export_service.send_download(content, export_service.build_filename(resource, extension), mime)


@frappe.whitelist()
def export_live_positions(device_ids=None, group_id=None, status=None, fmt="csv"):
	ensure_read()
	try:
		rows = positions.fetch_latest(device_ids=device_ids, group_id=group_id, status=status)
		content, mime, extension = export_service.build(
			rows, POSITION_COLUMNS, fmt, title=_("Live Positions")
		)
	except TraccarError as exc:
		return exc.as_dict()

	export_service.send_download(
		content, export_service.build_filename("live-positions", extension), mime
	)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_events(device_ids=None, group_ids=None, event_types=None, from_time=None, to_time=None, limit=None, offset=0):
	"""Backed by /reports/events - Traccar has no /events collection endpoint."""
	ensure_read()
	return events.list_events(
		device_ids=device_ids,
		group_ids=group_ids,
		event_types=event_types,
		from_time=from_time,
		to_time=to_time,
		limit=limit,
		offset=offset,
	)


@frappe.whitelist()
def get_event(event_id):
	ensure_read()
	return events.get_event(event_id)


# ---------------------------------------------------------------------------
# Geofences
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_geofence(geofence_id):
	ensure_read()
	return geofences.get_geofence(geofence_id)


@frappe.whitelist()
def save_geofence(payload, geofence_id=None):
	ensure_write()
	payload = parse_json_arg(payload, {})
	require(payload.get("name"), "Name")
	require(payload.get("area"), "Area")
	if geofence_id:
		return geofences.update_geofence(geofence_id, payload)
	return geofences.create_geofence(payload)


@frappe.whitelist()
def delete_geofence(geofence_id):
	ensure_write()
	return geofences.delete_geofence(geofence_id)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_notification_types(refresh=False):
	ensure_read()
	return notifications.get_notification_types(parse_bool(refresh))


@frappe.whitelist()
def get_notificators(announcement=False, refresh=False):
	ensure_read()
	return notifications.get_notificators(parse_bool(announcement), parse_bool(refresh))


@frappe.whitelist()
def save_notification(payload, notification_id=None):
	ensure_write()
	payload = parse_json_arg(payload, {})
	require(payload.get("type"), "Type")
	if notification_id:
		return notifications.update_notification(notification_id, payload)
	return notifications.create_notification(payload)


@frappe.whitelist()
def delete_notification(notification_id):
	ensure_write()
	return notifications.delete_notification(notification_id)


@frappe.whitelist()
def send_test_notification(notificator=None):
	ensure_write()
	return notifications.send_test_notification(notificator)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_command_types(device_id=None, text_channel=False, refresh=False):
	ensure_read()
	return commands.get_command_types(device_id, text_channel, parse_bool(refresh))


@frappe.whitelist()
def get_device_saved_commands(device_id):
	ensure_read()
	return commands.get_device_saved_commands(device_id)


@frappe.whitelist()
def save_command(payload, command_id=None):
	ensure_command()
	payload = parse_json_arg(payload, {})
	require(payload.get("type"), "Command Type")
	if command_id:
		return commands.update_command(command_id, payload)
	return commands.create_command(payload)


@frappe.whitelist()
def delete_command(command_id):
	ensure_command()
	return commands.delete_command(command_id)


@frappe.whitelist()
def send_command(device_id=None, command_type=None, attributes=None, saved_command_id=None, text_channel=False, group_id=None):
	"""Dispatch a command. Manager role only, on top of Traccar's own checks."""
	ensure_command()
	return commands.send_command(
		device_id=device_id,
		command_type=command_type,
		attributes=parse_json_arg(attributes, {}),
		saved_command_id=saved_command_id,
		text_channel=parse_bool(text_channel),
		group_id=group_id,
	)


# ---------------------------------------------------------------------------
# Drivers / maintenance / calendars / orders
# ---------------------------------------------------------------------------


@frappe.whitelist()
def save_driver(payload, driver_id=None):
	ensure_write()
	payload = parse_json_arg(payload, {})
	require(payload.get("name"), "Name")
	require(payload.get("uniqueId"), "Unique ID")
	if driver_id:
		return drivers.update_driver(driver_id, payload)
	return drivers.create_driver(payload)


@frappe.whitelist()
def delete_driver(driver_id):
	ensure_write()
	return drivers.delete_driver(driver_id)


@frappe.whitelist()
def save_maintenance(payload, item_id=None):
	ensure_write()
	payload = parse_json_arg(payload, {})
	require(payload.get("name"), "Name")
	require(payload.get("type"), "Type")
	if item_id:
		return maintenance.update_maintenance(item_id, payload)
	return maintenance.create_maintenance(payload)


@frappe.whitelist()
def delete_maintenance(item_id):
	ensure_write()
	return maintenance.delete_maintenance(item_id)


@frappe.whitelist()
def get_calendar(calendar_id):
	ensure_read()
	return calendars.get_calendar(calendar_id)


@frappe.whitelist()
def save_calendar(payload, calendar_id=None):
	ensure_write()
	payload = parse_json_arg(payload, {})
	require(payload.get("name"), "Name")
	require(payload.get("ical_text"), "Schedule")
	if calendar_id:
		return calendars.update_calendar(calendar_id, payload)
	return calendars.create_calendar(payload)


@frappe.whitelist()
def delete_calendar(calendar_id):
	ensure_write()
	return calendars.delete_calendar(calendar_id)


@frappe.whitelist()
def save_order(payload, order_id=None):
	ensure_admin()
	payload = parse_json_arg(payload, {})
	require(payload.get("uniqueId"), "Unique ID")
	if order_id:
		return orders.update_order(order_id, payload)
	return orders.create_order(payload)


@frappe.whitelist()
def delete_order(order_id):
	ensure_admin()
	return orders.delete_order(order_id)


# ---------------------------------------------------------------------------
# Server / statistics / audit
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_server_info(refresh=False):
	ensure_read()
	return server.get_server_info(parse_bool(refresh))


@frappe.whitelist()
def get_server_health():
	ensure_read()
	return server.check_health()


@frappe.whitelist()
def get_statistics(from_time, to_time):
	ensure_admin()
	return statistics.get_statistics(from_time, to_time)


@frappe.whitelist()
def get_audit_log(from_time, to_time, limit=None, offset=0):
	ensure_admin()
	return audit.get_audit_log(from_time, to_time, limit=limit, offset=offset)


@frappe.whitelist()
def export_audit_log(from_time, to_time, fmt="csv"):
	ensure_admin()
	try:
		rows = audit.fetch_actions(from_time, to_time)
		content, mime, extension = export_service.build(
			rows, AUDIT_COLUMNS, fmt, title=_("Audit Log")
		)
	except TraccarError as exc:
		return exc.as_dict()

	export_service.send_download(content, export_service.build_filename("audit-log", extension), mime)


@frappe.whitelist()
def reverse_geocode(latitude, longitude):
	ensure_read()
	return server.reverse_geocode(latitude, longitude)


# ---------------------------------------------------------------------------
# Live video (relayed so that no credential reaches the browser)
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_stream_playlist_url(device_id, channel=0):
	ensure_read()
	device_id = cint(require(device_id, "Device"))
	channel = cint(channel)
	base = "/api/method/erp_tracking.api.stream_playlist"
	return ok(
		{
			"playlist_url": f"{base}?device_id={device_id}&channel={channel}",
			"device_id": device_id,
			"channel": channel,
		}
	)


@frappe.whitelist()
def stream_playlist(device_id, channel=0):
	ensure_read()
	device_id = cint(device_id)
	channel = cint(channel)
	rewrite_base = (
		f"/api/method/erp_tracking.api.stream_segment?device_id={device_id}&channel={channel}"
	)
	try:
		playlist = stream.fetch_playlist(device_id, channel, rewrite_base)
	except TraccarError as exc:
		frappe.local.response.http_status_code = exc.status_code or 502
		return exc.as_dict()

	frappe.local.response.type = "binary"
	frappe.local.response.filename = "live.m3u8"
	frappe.local.response.filecontent = playlist.encode("utf-8")
	return


@frappe.whitelist()
def stream_segment(device_id, channel=0, index=0):
	ensure_read()
	try:
		content = stream.fetch_segment(device_id, channel, index)
	except TraccarError as exc:
		frappe.local.response.http_status_code = exc.status_code or 502
		return exc.as_dict()

	frappe.local.response.type = "binary"
	frappe.local.response.filename = f"{cint(index)}.ts"
	frappe.local.response.filecontent = content
	return
