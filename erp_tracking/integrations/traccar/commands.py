"""Commands - saved commands, command types and dispatch.

``POST /commands/send`` answers 200 when the command reached the device and 202
when Traccar queued it because the device is offline.  Both are surfaced
distinctly in the UI.
"""

from frappe import _
from frappe.utils import cint, cstr

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_list
from erp_tracking.integrations.traccar.utils import (
	cached,
	parse_bool,
	require,
	standard_response,
	stringify_attributes,
)


@standard_response
def list_commands(filters=None, refresh=False):
	return fetch_list("commands", filters=filters, refresh=refresh)


@standard_response
def get_command(command_id):
	command_id = cint(require(command_id, "Command"))
	return get_client().get(TRACCAR_ENDPOINTS["command"].format(id=command_id))


@standard_response
def create_command(payload):
	return get_client().post(TRACCAR_ENDPOINTS["commands"], json_body=payload)


@standard_response
def update_command(command_id, payload):
	command_id = cint(require(command_id, "Command"))
	payload = dict(payload or {})
	payload["id"] = command_id
	return get_client().put(TRACCAR_ENDPOINTS["command"].format(id=command_id), json_body=payload)


@standard_response
def delete_command(command_id):
	command_id = cint(require(command_id, "Command"))
	get_client().delete(TRACCAR_ENDPOINTS["command"].format(id=command_id))
	return {"deleted": command_id}


@standard_response
def get_command_types(device_id=None, text_channel=False, refresh=False):
	"""GET /commands/types - device specific when ``deviceId`` is supplied."""
	params = {}
	if device_id:
		params["deviceId"] = cint(device_id)
	if parse_bool(text_channel):
		params["textChannel"] = "true"

	def _call():
		return get_client().get(TRACCAR_ENDPOINTS["command_types"], params) or []

	types = cached(("command_types", params.get("deviceId"), params.get("textChannel")), 600, _call, refresh)
	return [{"type": t.get("type"), "label": _(cstr(t.get("type")))} for t in types or []]


@standard_response
def get_device_saved_commands(device_id):
	"""GET /commands/send - saved commands the device's protocol supports."""
	device_id = cint(require(device_id, "Device"))
	rows = get_client().get(TRACCAR_ENDPOINTS["command_send"], {"deviceId": device_id}) or []
	return stringify_attributes(rows)


def send(device_id=None, command_type=None, attributes=None, saved_command_id=None, text_channel=False, group_id=None):
	"""POST /commands/send.

	Either ``saved_command_id`` (Traccar re-uses the stored command) or
	``command_type`` must be given.
	"""
	body = {}
	if saved_command_id:
		body["id"] = cint(saved_command_id)
	else:
		body["type"] = cstr(require(command_type, "Command Type"))

	if device_id:
		body["deviceId"] = cint(device_id)
	if parse_bool(text_channel):
		body["textChannel"] = True
	if attributes:
		body["attributes"] = attributes

	if not body.get("deviceId") and not group_id:
		from erp_tracking.integrations.traccar.exceptions import TraccarAPIError

		raise TraccarAPIError(_("Select a device or a group."), 400)

	params = {"groupId": cint(group_id)} if group_id else None
	client = get_client()

	# The client returns the parsed body; 202 is distinguished by Traccar
	# returning a QueuedCommand payload, so the raw status is needed here.
	import time

	import requests

	started = time.monotonic()
	url = client.base_url + TRACCAR_ENDPOINTS["command_send"]
	headers = {"Accept": "application/json", **client.auth.get_auth_headers()}
	try:
		response = requests.post(
			url, params=params, json=body, headers=headers, timeout=client.timeout, verify=client.verify_ssl
		)
	except requests.Timeout as exc:
		from erp_tracking.integrations.traccar.exceptions import TraccarTimeoutError
		from erp_tracking.integrations.traccar.utils import redact

		raise TraccarTimeoutError(detail=redact(str(exc)))
	except requests.RequestException as exc:
		from erp_tracking.integrations.traccar.exceptions import TraccarConnectionError
		from erp_tracking.integrations.traccar.utils import redact

		raise TraccarConnectionError(detail=redact(str(exc)))

	client._log("POST", TRACCAR_ENDPOINTS["command_send"], response.status_code, started)
	client._raise_for_status(response)

	try:
		payload = response.json()
	except ValueError:
		payload = None

	queued = response.status_code == 202
	return {
		"queued": queued,
		"status_code": response.status_code,
		"command": payload,
		"message": _("Command queued") if queued else _("Command sent"),
	}


@standard_response
def send_command(**kwargs):
	return send(**kwargs)
