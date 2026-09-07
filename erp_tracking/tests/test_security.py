"""Security tests: role enforcement, allow-lists and secret containment."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erp_tracking import api
from erp_tracking.permissions import ROLE_MANAGER, ROLE_USER, ROLE_VIEWER
from erp_tracking.tests.test_auth import make_settings

DEVICES = [{"id": 1, "name": "Truck 001", "status": "online"}]


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@")[0]
		user.enabled = 1
		user.insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	user.set("roles", [])
	for role in roles:
		user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	return email


class TestSecurity(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		make_settings()
		self.viewer = make_user("erpt-viewer@example.com", [ROLE_VIEWER])
		self.user = make_user("erpt-user@example.com", [ROLE_USER])
		self.manager = make_user("erpt-manager@example.com", [ROLE_MANAGER])
		self.outsider = make_user("erpt-outsider@example.com", [])

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_unauthorised_user_cannot_read(self):
		frappe.set_user(self.outsider)
		with self.assertRaises(frappe.PermissionError):
			api.get_devices()

	def test_viewer_can_read(self):
		frappe.set_user(self.viewer)
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", return_value=DEVICES):
			response = api.get_devices()
		self.assertTrue(response["success"])

	def test_viewer_cannot_send_commands(self):
		frappe.set_user(self.viewer)
		with self.assertRaises(frappe.PermissionError):
			api.send_command(device_id=1, command_type="engineStop")

	def test_user_cannot_send_commands(self):
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			api.send_command(device_id=1, command_type="engineStop")

	def test_user_cannot_read_audit_log(self):
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			api.get_audit_log("2026-08-01", "2026-08-02")

	def test_user_cannot_test_connection(self):
		frappe.set_user(self.user)
		with self.assertRaises(frappe.PermissionError):
			api.test_connection()

	def test_manager_may_send_commands(self):
		frappe.set_user(self.manager)
		with patch(
			"erp_tracking.integrations.traccar.commands.send",
			return_value={"queued": False, "status_code": 200, "command": {}, "message": "Command sent"},
		):
			response = api.send_command(device_id=1, command_type="engineStop")
		self.assertTrue(response["success"])

	def test_invalid_report_name_rejected(self):
		frappe.set_user(self.manager)
		response = api.run_report("../../secrets", frappe.as_json({"from": "2026-08-01", "to": "2026-08-02"}))
		self.assertFalse(response["success"])
		self.assertEqual(response["status_code"], 400)

	def test_invalid_resource_rejected(self):
		frappe.set_user(self.manager)
		response = api.get_list("passwords")
		self.assertFalse(response["success"])

	def test_configuration_state_hides_secrets(self):
		frappe.set_user(self.manager)
		payload = frappe.as_json(api.get_configuration_state())
		for secret in ("secret", "token-123", "Authorization", "Bearer", "Basic "):
			self.assertNotIn(secret, payload)

	def test_test_connection_never_returns_credentials(self):
		frappe.set_user("Administrator")
		with patch(
			"erp_tracking.integrations.traccar.auth.TraccarAuth.authenticate",
			return_value={"id": 1, "email": "fleet@example.com"},
		), patch(
			"erp_tracking.integrations.traccar.server.get_server_info.raw",
			return_value={"version": "6.14.5"},
		):
			result = api.test_connection()
		payload = frappe.as_json(result)
		self.assertTrue(result["success"])
		self.assertNotIn("secret", payload)
		self.assertNotIn("token-123", payload)

	def test_user_list_strips_passwords(self):
		frappe.set_user("Administrator")
		users = [{"id": 1, "name": "Fleet", "email": "f@example.com", "password": "hash", "attributes": {"k": "v"}}]
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", return_value=users):
			response = api.get_users()
		row = response["data"]["items"][0]
		self.assertNotIn("password", row)
		self.assertNotIn("attributes", row)
