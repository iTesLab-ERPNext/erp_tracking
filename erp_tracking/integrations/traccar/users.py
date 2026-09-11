"""Users - full CRUD over /users and /users/{id}.

Passwords are handled write-only end to end: a password is required to
create a Traccar account, optional on update (omitted entirely from the
outgoing payload means "leave unchanged" rather than "clear it"), and never
appears in any response - :meth:`TraccarAuth.sanitize_user` strips it (and
``attributes``/``token``) from every row this module returns, matching the
existing read path.
"""

from frappe.utils import cint

from erp_tracking.integrations.traccar.auth import TraccarAuth
from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.listing import fetch_list
from erp_tracking.integrations.traccar.utils import require, standard_response


@standard_response
def list_users(filters=None, refresh=False):
	return fetch_list("users", filters=filters, refresh=refresh)


@standard_response
def get_user(user_id):
	user_id = cint(require(user_id, "User"))
	user = get_client().get(TRACCAR_ENDPOINTS["user"].format(id=user_id))
	return TraccarAuth.sanitize_user(user)


@standard_response
def create_user(payload):
	payload = dict(payload or {})
	require(payload.get("password"), "Password")
	user = get_client().post(TRACCAR_ENDPOINTS["users"], json_body=payload)
	return TraccarAuth.sanitize_user(user)


@standard_response
def update_user(user_id, payload):
	"""``payload`` should omit ``password`` entirely when it is not being
	changed - a blank/omitted password here is never sent to Traccar, so an
	existing password is left untouched rather than being blanked out.
	"""
	user_id = cint(require(user_id, "User"))
	payload = dict(payload or {})
	payload["id"] = user_id
	if not payload.get("password"):
		payload.pop("password", None)
	user = get_client().put(TRACCAR_ENDPOINTS["user"].format(id=user_id), json_body=payload)
	return TraccarAuth.sanitize_user(user)


@standard_response
def delete_user(user_id):
	user_id = cint(require(user_id, "User"))
	get_client().delete(TRACCAR_ENDPOINTS["user"].format(id=user_id))
	return {"deleted": user_id}
