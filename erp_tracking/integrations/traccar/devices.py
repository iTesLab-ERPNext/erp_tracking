"""Devices - GET/POST/PUT/DELETE /devices, /devices/{id}, accumulators."""

from frappe import _
from frappe.utils import cint

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_all, fetch_list
from erp_tracking.integrations.traccar.utils import require, standard_response


@standard_response
def list_devices(filters=None, refresh=False):
	return fetch_list("devices", filters=filters, refresh=refresh)


@standard_response
def get_device(device_id):
	device_id = cint(require(device_id, "Device"))
	return get_client().get(TRACCAR_ENDPOINTS["device"].format(id=device_id))


@standard_response
def create_device(payload):
	return get_client().post(TRACCAR_ENDPOINTS["devices"], json_body=payload)


@standard_response
def update_device(device_id, payload):
	device_id = cint(require(device_id, "Device"))
	payload = dict(payload or {})
	payload["id"] = device_id
	return get_client().put(TRACCAR_ENDPOINTS["device"].format(id=device_id), json_body=payload)


@standard_response
def delete_device(device_id):
	device_id = cint(require(device_id, "Device"))
	get_client().delete(TRACCAR_ENDPOINTS["device"].format(id=device_id))
	return {"deleted": device_id}


@standard_response
def update_accumulators(device_id, total_distance=None, hours=None):
	"""PUT /devices/{id}/accumulators - odometer and engine hours."""
	device_id = cint(require(device_id, "Device"))
	body = {"deviceId": device_id}
	if total_distance is not None:
		body["totalDistance"] = float(total_distance)
	if hours is not None:
		body["hours"] = float(hours)

	get_client().put(TRACCAR_ENDPOINTS["device_accumulators"].format(id=device_id), json_body=body)
	return {"deviceId": device_id}


def device_map(refresh=False):
	"""``{id: device}`` used to resolve device names in positions and reports."""
	devices = fetch_all("devices", {"excludeAttributes": True})
	return {cint(d.get("id")): d for d in devices}


def device_choices(refresh=False):
	"""Lightweight ``[{value, label, status, groupId}]`` list for filter fields."""
	devices = fetch_all("devices", {"excludeAttributes": True})
	return [
		{
			"value": cint(d.get("id")),
			"label": d.get("name") or d.get("uniqueId") or _("Device {0}").format(d.get("id")),
			"status": d.get("status"),
			"groupId": d.get("groupId"),
			"disabled": d.get("disabled"),
		}
		for d in devices
	]
