"""Commands feature module (Sections 24-26).

Saved commands (list/get/create/update/delete) mirror /commands CRUD.
Command types come from /commands/types. Sending a command - either a new
one-off or a saved command by id - goes through /commands/send.

Section 25 is explicit: "Never allow unauthorized users to send commands.
Implement strict permission checking." Role enforcement itself lives in
api.py (require_admin() wraps every write/send call here) - this module
stays focused on the Traccar request shape, but every mutating function
here is only ever reached through an admin-gated whitelisted method.
"""

from __future__ import annotations

import frappe

from .client import TraccarClient
from .utils import paginate_params

REFERENCE_CACHE_TTL_SECONDS = 3600


def get_commands(
	keyword: str | None = None,
	device_id: int | None = None,
	group_id: int | None = None,
	limit: int | None = None,
	offset: int | None = None,
	refresh: bool = False,
) -> dict:
	cache_key = f"erp_tracking:commands:{keyword}:{device_id}:{group_id}:{limit}:{offset}"
	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached

	params = paginate_params(limit, offset)
	if keyword:
		params["keyword"] = keyword
	if device_id:
		params["deviceId"] = int(device_id)
	if group_id:
		params["groupId"] = int(group_id)

	result = TraccarClient().request_safe("GET", "commands", params=params)
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=60)
	return result


def get_command(command_id: int) -> dict:
	return TraccarClient().request_safe("GET", "command", path_params={"id": command_id})


def get_command_types(device_id: int | None = None, text_channel: bool | None = None, refresh: bool = False) -> dict:
	"""GET /commands/types - available command types, optionally scoped to
	a device (Section 26: "Support device-specific command types where
	provided by the API").
	"""
	cache_key = f"erp_tracking:command_types:{device_id}:{text_channel}"
	if not refresh:
		cached = frappe.cache().get_value(cache_key)
		if cached is not None:
			return cached

	params = {}
	if device_id:
		params["deviceId"] = int(device_id)
	if text_channel is not None:
		params["textChannel"] = bool(text_channel)

	result = TraccarClient().request_safe("GET", "commands_types", params=params)
	if result["success"]:
		frappe.cache().set_value(cache_key, result, expires_in_sec=REFERENCE_CACHE_TTL_SECONDS)
	return result


def get_available_commands_for_device(device_id: int) -> dict:
	"""GET /commands/send?deviceId= - saved commands actually supported by
	this device's protocol right now (Section 24: "Saved commands").
	"""
	return TraccarClient().request_safe("GET", "commands_send", params={"deviceId": int(device_id)})


def _invalidate_cache():
	frappe.cache().delete_keys("erp_tracking:commands:")


def create_saved_command(device_id: int | None, description: str, type_: str, text_channel: bool = False, attributes: dict | None = None) -> dict:
	payload = {"description": description, "type": type_, "textChannel": bool(text_channel)}
	if device_id:
		payload["deviceId"] = int(device_id)
	if attributes:
		payload["attributes"] = attributes

	result = TraccarClient().request_safe("POST", "commands", json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def update_saved_command(command_id: int, **fields) -> dict:
	payload = {"id": int(command_id), **fields}
	result = TraccarClient().request_safe("PUT", "command", path_params={"id": command_id}, json=payload)
	if result["success"]:
		_invalidate_cache()
	return result


def delete_saved_command(command_id: int) -> dict:
	result = TraccarClient().request_safe("DELETE", "command", path_params={"id": command_id})
	if result["success"]:
		_invalidate_cache()
	return result


def send_command(
	device_id: int | None = None,
	group_id: int | None = None,
	saved_command_id: int | None = None,
	type_: str | None = None,
	text_channel: bool = False,
	attributes: dict | None = None,
) -> dict:
	"""POST /commands/send - Section 25.

	Either dispatch a saved command (pass saved_command_id, which becomes
	body.id per the spec: "Dispatch a new command or Saved Command if
	body.id set") or a one-off command (pass device_id + type_). group_id
	sends to every device in the group, per the spec's groupId query param.

	Returns success=True with status_code 200 ("Command sent") or 202
	("Command queued") - both are success outcomes, distinguished by
	status_code so the UI can show the right message (Section 25).
	"""
	if not saved_command_id and not type_:
		return _client_error("Either a saved command or a command type is required.")
	if not device_id and not group_id and not saved_command_id:
		return _client_error("A device or group is required to send a command.")

	payload = {}
	if saved_command_id:
		payload["id"] = int(saved_command_id)
	if device_id:
		payload["deviceId"] = int(device_id)
	if type_:
		payload["type"] = type_
	payload["textChannel"] = bool(text_channel)
	if attributes:
		payload["attributes"] = attributes

	params = {}
	if group_id:
		params["groupId"] = int(group_id)

	return TraccarClient().request_safe("POST", "commands_send", params=params, json=payload)


def _client_error(message: str) -> dict:
	return {
		"success": False,
		"data": None,
		"message": message,
		"status_code": 400,
		"error": "TraccarClientValidationError",
	}
