"""Notifications - CRUD, types, notificators and test delivery."""

from frappe import _
from frappe.utils import cint, cstr

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_list
from erp_tracking.integrations.traccar.utils import cached, parse_bool, require, standard_response


@standard_response
def list_notifications(filters=None, refresh=False):
	return fetch_list("notifications", filters=filters, refresh=refresh)


@standard_response
def get_notification(notification_id):
	notification_id = cint(require(notification_id, "Notification"))
	return get_client().get(TRACCAR_ENDPOINTS["notification"].format(id=notification_id))


@standard_response
def create_notification(payload):
	return get_client().post(TRACCAR_ENDPOINTS["notifications"], json_body=payload)


@standard_response
def update_notification(notification_id, payload):
	notification_id = cint(require(notification_id, "Notification"))
	payload = dict(payload or {})
	payload["id"] = notification_id
	return get_client().put(
		TRACCAR_ENDPOINTS["notification"].format(id=notification_id), json_body=payload
	)


@standard_response
def delete_notification(notification_id):
	notification_id = cint(require(notification_id, "Notification"))
	get_client().delete(TRACCAR_ENDPOINTS["notification"].format(id=notification_id))
	return {"deleted": notification_id}


@standard_response
def get_notification_types(refresh=False):
	def _call():
		return get_client().get(TRACCAR_ENDPOINTS["notification_types"]) or []

	types = cached(("notification_types",), 3600, _call, refresh)
	return [{"type": t.get("type"), "label": _(cstr(t.get("type")))} for t in types or []]


@standard_response
def get_notificators(announcement=False, refresh=False):
	params = {"announcement": "true"} if parse_bool(announcement) else None

	def _call():
		return get_client().get(TRACCAR_ENDPOINTS["notificators"], params) or []

	items = cached(("notificators", bool(params)), 3600, _call, refresh)
	return [{"type": t.get("type"), "label": _(cstr(t.get("type")))} for t in items or []]


@standard_response
def send_test_notification(notificator=None):
	"""POST /notifications/test or /notifications/test/{notificator}."""
	if notificator:
		endpoint = f"{TRACCAR_ENDPOINTS['notification_test']}/{cstr(notificator)}"
	else:
		endpoint = TRACCAR_ENDPOINTS["notification_test"]
	get_client().post(endpoint)
	return {"sent": True}
