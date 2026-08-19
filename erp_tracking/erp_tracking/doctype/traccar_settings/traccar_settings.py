# Copyright (c) 2026, Your Company and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from erp_tracking.integrations.traccar.auth import TraccarAuth
from erp_tracking.integrations.traccar.client import TraccarClient
from erp_tracking.integrations.traccar.exceptions import (
	TraccarAPIError,
	TraccarAuthenticationError,
	TraccarConfigurationError,
	TraccarConnectionError,
	TraccarTimeoutError,
)


class TraccarSettings(Document):
	def validate(self):
		if self.auth_type == "Basic Auth" and not (self.username and self.get_password("password", raise_exception=False)):
			frappe.throw(_("Username and Password are required for Basic Auth."))

		if self.auth_type == "API Key" and not self.get_password("api_key", raise_exception=False):
			frappe.throw(_("API Key is required for API Key authentication."))

	def on_update(self):
		# Credentials may have changed - drop any cached auth state so the
		# very next request re-reads fresh settings instead of a stale copy.
		TraccarAuth().clear_session()


@frappe.whitelist()
def test_connection():
	"""Whitelisted backend method behind the "Test Connection" button.

	Never returns credentials or tokens - only a boolean/status summary,
	per Section 6 of the brief. Also persists the outcome onto Traccar
	Settings (connection_status / last_connection_test / last_error) so the
	Desk form reflects the last known state without re-testing.
	"""
	frappe.only_for("System Manager", "ERP Tracking Manager")

	settings = frappe.get_single("Traccar Settings")
	result = {
		"success": False,
		"authenticated": False,
		"status_code": None,
		"message": "",
	}
	status_label = "Invalid Configuration"

	try:
		client = TraccarClient()
		# /server is unauthenticated per the spec (security: []), so a
		# successful call here only proves the URL is reachable. /session
		# (GET) is what actually round-trips through auth, so we use that
		# to prove BOTH connectivity and authentication in one call.
		response = client.request("GET", "session")

		result["success"] = True
		result["authenticated"] = True
		result["status_code"] = response["status_code"]
		result["message"] = _("Connection successful")
		status_label = "Connected"

	except TraccarAuthenticationError as exc:
		result["status_code"] = exc.status_code
		result["message"] = _("Authentication failed")
		status_label = "Authentication Failed"

	except TraccarTimeoutError as exc:
		result["status_code"] = exc.status_code
		result["message"] = _("Connection timeout")
		status_label = "Timeout"

	except TraccarConnectionError as exc:
		result["status_code"] = exc.status_code
		result["message"] = _("Server unavailable")
		status_label = "Server Unavailable"

	except TraccarConfigurationError as exc:
		result["message"] = exc.message
		status_label = "Invalid Configuration"

	except TraccarAPIError as exc:
		result["status_code"] = exc.status_code
		result["message"] = exc.message
		status_label = "Server Unavailable"

	settings.db_set("connection_status", status_label, notify=True)
	settings.db_set("last_connection_test", frappe.utils.now_datetime(), notify=True)
	settings.db_set("last_error", "" if result["success"] else result["message"], notify=True)

	return result
