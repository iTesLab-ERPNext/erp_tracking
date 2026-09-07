"""Groups - GET/POST/PUT/DELETE /groups and /groups/{id}."""

from frappe.utils import cint

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_all, fetch_list
from erp_tracking.integrations.traccar.utils import require, standard_response


@standard_response
def list_groups(filters=None, refresh=False):
	return fetch_list("groups", filters=filters, refresh=refresh)


@standard_response
def get_group(group_id):
	group_id = cint(require(group_id, "Group"))
	return get_client().get(TRACCAR_ENDPOINTS["group"].format(id=group_id))


@standard_response
def get_group_devices(group_id, filters=None):
	"""Devices whose ``groupId`` matches - /devices has no groupId parameter."""
	group_id = cint(require(group_id, "Group"))
	devices = fetch_all("devices", {"excludeAttributes": True})
	return [d for d in devices if cint(d.get("groupId")) == group_id]


@standard_response
def create_group(payload):
	return get_client().post(TRACCAR_ENDPOINTS["groups"], json_body=payload)


@standard_response
def update_group(group_id, payload):
	group_id = cint(require(group_id, "Group"))
	payload = dict(payload or {})
	payload["id"] = group_id
	return get_client().put(TRACCAR_ENDPOINTS["group"].format(id=group_id), json_body=payload)


@standard_response
def delete_group(group_id):
	group_id = cint(require(group_id, "Group"))
	get_client().delete(TRACCAR_ENDPOINTS["group"].format(id=group_id))
	return {"deleted": group_id}


def group_choices():
	groups = fetch_all("groups")
	return [{"value": cint(g.get("id")), "label": g.get("name")} for g in groups]
