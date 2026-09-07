"""Users - read-only surface over GET /users and GET /users/{id}.

Traccar exposes POST/PUT/DELETE on /users, but this app keeps user
administration inside Traccar itself: creating Traccar accounts from ERPNext
would mean accepting a password through a Frappe endpoint.
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
