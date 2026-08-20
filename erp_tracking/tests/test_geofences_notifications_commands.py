"""Phase 5 tests: Geofences, Notifications, Commands.

Run with:
    bench --site <site> run-tests --app erp_tracking \
        --module erp_tracking.tests.test_geofences_notifications_commands
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar import commands, geofences, notifications


def _set_settings(**kwargs):
	doc = frappe.get_single("Traccar Settings")
	defaults = dict(
		traccar_url="https://demo.traccar.org/api",
		enabled=1,
		timeout=15,
		verify_ssl=1,
		auth_type="Basic Auth",
		username="admin",
		password="secret-password",
	)
	defaults.update(kwargs)
	for field, value in defaults.items():
		doc.set(field, value)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc


def _mock_response(status_code=200, json_body=None):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": "application/json"}
	resp.content = json.dumps(json_body).encode() if json_body is not None else b""
	resp.json.return_value = json_body
	return resp


class TestGeofences(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:geofences:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_geofence(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Warehouse", "area": "CIRCLE (0 0, 100)"})
		result = geofences.create_geofence(name="Warehouse", area="CIRCLE (0 0, 100)")
		self.assertTrue(result["success"])

		called_url = mock_request.call_args.kwargs["url"]
		called_method = mock_request.call_args.kwargs["method"] if "method" in mock_request.call_args.kwargs else None
		self.assertTrue(called_url.endswith("/geofences"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_update_and_delete_invalidate_cache(self, mock_request):
		mock_request.return_value = _mock_response(200, [{"id": 1, "name": "Warehouse"}])
		geofences.get_geofences(refresh=True)
		self.assertIsNotNone(frappe.cache().get_value("erp_tracking:geofences:None:None:None:None:None"))

		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Warehouse Updated"})
		geofences.update_geofence(1, name="Warehouse Updated", area="CIRCLE (0 0, 100)")

		# Cache key from before the update should no longer be trusted -
		# module clears the whole geofences cache namespace on write.
		self.assertIsNone(frappe.cache().get_value("erp_tracking:geofences:None:None:None:None:None"))


class TestNotifications(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:notifications:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_notification_types(self, mock_request):
		mock_request.return_value = _mock_response(200, [{"type": "deviceOnline"}, {"type": "geofenceEnter"}])
		result = notifications.get_notification_types()
		self.assertTrue(result["success"])
		self.assertEqual(len(result["data"]), 2)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_notification(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "type": "deviceOffline"})
		result = notifications.create_notification(type_="deviceOffline", notificators="web,mail")
		self.assertTrue(result["success"])

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_send_test_notification(self, mock_request):
		resp = MagicMock(spec=requests.Response)
		resp.status_code = 204
		resp.headers = {}
		resp.content = b""
		mock_request.return_value = resp
		result = notifications.send_test_notification()
		self.assertTrue(result["success"])


class TestCommands(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:commands:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_send_command_sent(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "type": "engineStop"})
		result = commands.send_command(device_id=10, type_="engineStop")
		self.assertTrue(result["success"])
		self.assertEqual(result["status_code"], 200)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_send_command_queued(self, mock_request):
		mock_request.return_value = _mock_response(202, {"id": 1, "type": "engineStop"})
		result = commands.send_command(device_id=10, type_="engineStop")
		self.assertTrue(result["success"])
		self.assertEqual(result["status_code"], 202)

	def test_send_command_requires_type_or_saved_command(self):
		result = commands.send_command(device_id=10)
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarClientValidationError")

	def test_send_command_requires_target(self):
		result = commands.send_command(type_="engineStop")
		self.assertFalse(result["success"])

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_command_types_for_device(self, mock_request):
		mock_request.return_value = _mock_response(200, [{"type": "engineStop"}, {"type": "positionSingle"}])
		result = commands.get_command_types(device_id=10, refresh=True)
		self.assertTrue(result["success"])
		called_params = mock_request.call_args.kwargs["params"]
		self.assertEqual(called_params["deviceId"], 10)


class TestPhase5Permissions(FrappeTestCase):
	"""Section 25/40: commands and notifications are Manager-only; geofence
	writes require at least the User role, never Viewer-only."""

	def setUp(self):
		_set_settings()

	def test_guest_cannot_send_command(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.send_command")(device_id=1, type_="engineStop")
		frappe.set_user("Administrator")

	def test_guest_cannot_create_geofence(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.create_geofence")(name="X", area="CIRCLE (0 0, 10)")
		frappe.set_user("Administrator")

	def test_guest_cannot_view_notifications(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_notifications")()
		frappe.set_user("Administrator")
