"""Geofences - full CRUD, all four verbs are defined in the specification."""

from frappe.utils import cint

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_all, fetch_list
from erp_tracking.integrations.traccar.utils import require, standard_response, wkt_shape


@standard_response
def list_geofences(filters=None, refresh=False):
	return fetch_list("geofences", filters=filters, refresh=refresh)


@standard_response
def get_geofence(geofence_id):
	geofence_id = cint(require(geofence_id, "Geofence"))
	geofence = get_client().get(TRACCAR_ENDPOINTS["geofence"].format(id=geofence_id)) or {}
	geofence["shape"] = wkt_shape(geofence.get("area"))
	return geofence


@standard_response
def create_geofence(payload):
	return get_client().post(TRACCAR_ENDPOINTS["geofences"], json_body=payload)


@standard_response
def update_geofence(geofence_id, payload):
	geofence_id = cint(require(geofence_id, "Geofence"))
	payload = dict(payload or {})
	payload["id"] = geofence_id
	return get_client().put(TRACCAR_ENDPOINTS["geofence"].format(id=geofence_id), json_body=payload)


@standard_response
def delete_geofence(geofence_id):
	geofence_id = cint(require(geofence_id, "Geofence"))
	get_client().delete(TRACCAR_ENDPOINTS["geofence"].format(id=geofence_id))
	return {"deleted": geofence_id}


def geofence_choices():
	return [{"value": cint(g.get("id")), "label": g.get("name")} for g in fetch_all("geofences")]
