"""Drivers - GET/POST/PUT/DELETE /drivers and /drivers/{id}."""

from frappe.utils import cint

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_list
from erp_tracking.integrations.traccar.utils import require, standard_response


@standard_response
def list_drivers(filters=None, refresh=False):
	return fetch_list("drivers", filters=filters, refresh=refresh)


@standard_response
def get_driver(driver_id):
	driver_id = cint(require(driver_id, "Driver"))
	return get_client().get(TRACCAR_ENDPOINTS["driver"].format(id=driver_id))


@standard_response
def create_driver(payload):
	return get_client().post(TRACCAR_ENDPOINTS["drivers"], json_body=payload)


@standard_response
def update_driver(driver_id, payload):
	driver_id = cint(require(driver_id, "Driver"))
	payload = dict(payload or {})
	payload["id"] = driver_id
	return get_client().put(TRACCAR_ENDPOINTS["driver"].format(id=driver_id), json_body=payload)


@standard_response
def delete_driver(driver_id):
	driver_id = cint(require(driver_id, "Driver"))
	get_client().delete(TRACCAR_ENDPOINTS["driver"].format(id=driver_id))
	return {"deleted": driver_id}
