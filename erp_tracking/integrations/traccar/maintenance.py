"""Maintenance - GET/POST/PUT/DELETE /maintenance and /maintenance/{id}."""

from frappe.utils import cint

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_list
from erp_tracking.integrations.traccar.utils import require, standard_response


@standard_response
def list_maintenance(filters=None, refresh=False):
	return fetch_list("maintenance", filters=filters, refresh=refresh)


@standard_response
def get_maintenance(item_id):
	item_id = cint(require(item_id, "Maintenance"))
	return get_client().get(TRACCAR_ENDPOINTS["maintenance_item"].format(id=item_id))


@standard_response
def create_maintenance(payload):
	return get_client().post(TRACCAR_ENDPOINTS["maintenance"], json_body=payload)


@standard_response
def update_maintenance(item_id, payload):
	item_id = cint(require(item_id, "Maintenance"))
	payload = dict(payload or {})
	payload["id"] = item_id
	return get_client().put(TRACCAR_ENDPOINTS["maintenance_item"].format(id=item_id), json_body=payload)


@standard_response
def delete_maintenance(item_id):
	item_id = cint(require(item_id, "Maintenance"))
	get_client().delete(TRACCAR_ENDPOINTS["maintenance_item"].format(id=item_id))
	return {"deleted": item_id}
