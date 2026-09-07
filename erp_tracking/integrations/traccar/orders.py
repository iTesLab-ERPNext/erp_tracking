"""Orders - GET/POST/PUT/DELETE /orders and /orders/{id}."""

from frappe.utils import cint

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_list
from erp_tracking.integrations.traccar.utils import require, standard_response


@standard_response
def list_orders(filters=None, refresh=False):
	return fetch_list("orders", filters=filters, refresh=refresh)


@standard_response
def get_order(order_id):
	order_id = cint(require(order_id, "Order"))
	return get_client().get(TRACCAR_ENDPOINTS["order"].format(id=order_id))


@standard_response
def create_order(payload):
	return get_client().post(TRACCAR_ENDPOINTS["orders"], json_body=payload)


@standard_response
def update_order(order_id, payload):
	order_id = cint(require(order_id, "Order"))
	payload = dict(payload or {})
	payload["id"] = order_id
	return get_client().put(TRACCAR_ENDPOINTS["order"].format(id=order_id), json_body=payload)


@standard_response
def delete_order(order_id):
	order_id = cint(require(order_id, "Order"))
	get_client().delete(TRACCAR_ENDPOINTS["order"].format(id=order_id))
	return {"deleted": order_id}
