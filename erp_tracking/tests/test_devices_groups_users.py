"""Phase 2 tests: Devices, Groups, Users, Dashboard.

Run with:
    bench --site <site> run-tests --app erp_tracking \
        --module erp_tracking.tests.test_devices_groups_users
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar import dashboard, devices, groups, users


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


class TestDevices(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:devices:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_list_devices(self, mock_request):
		mock_request.return_value = _mock_response(
			200,
			[
				{"id": 1, "name": "Truck 001", "status": "online"},
				{"id": 2, "name": "Truck 002", "status": "offline"},
			],
		)
		result = devices.get_devices(refresh=True)
		self.assertTrue(result["success"])
		self.assertEqual(len(result["data"]), 2)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_device(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Truck 001"})
		result = devices.get_device(1)
		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["name"], "Truck 001")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_devices_api_error(self, mock_request):
		mock_request.return_value = _mock_response(404)
		result = devices.get_device(999)
		self.assertFalse(result["success"])
		self.assertEqual(result["status_code"], 404)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_count_devices_online_offline(self, mock_request):
		mock_request.return_value = _mock_response(
			200,
			[
				{"id": 1, "status": "online"},
				{"id": 2, "status": "online"},
				{"id": 3, "status": "offline"},
			],
		)
		result = devices.count_devices()
		self.assertTrue(result["success"])
		self.assertEqual(result["data"], {"total": 3, "online": 2, "offline": 1})


class TestGroups(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:groups:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_list_groups(self, mock_request):
		mock_request.return_value = _mock_response(200, [{"id": 1, "name": "Fleet A"}])
		result = groups.get_groups(refresh=True)
		self.assertTrue(result["success"])
		self.assertEqual(result["data"][0]["name"], "Fleet A")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_devices_in_group_filters_correctly(self, mock_request):
		mock_request.return_value = _mock_response(
			200,
			[
				{"id": 1, "name": "Truck 001", "groupId": 5},
				{"id": 2, "name": "Truck 002", "groupId": 6},
			],
		)
		result = groups.devices_in_group(5)
		self.assertTrue(result["success"])
		self.assertEqual(len(result["data"]), 1)
		self.assertEqual(result["data"][0]["name"], "Truck 001")


class TestUsers(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:users:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_list_users_strips_password(self, mock_request):
		mock_request.return_value = _mock_response(
			200,
			[{"id": 1, "name": "Admin", "email": "admin@example.com", "password": "should-not-leak"}],
		)
		result = users.get_users(refresh=True)
		self.assertTrue(result["success"])
		self.assertNotIn("password", result["data"][0])
		dumped = json.dumps(result)
		self.assertNotIn("should-not-leak", dumped)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_user_strips_password(self, mock_request):
		mock_request.return_value = _mock_response(
			200, {"id": 1, "name": "Admin", "password": "should-not-leak"}
		)
		result = users.get_user(1)
		self.assertNotIn("password", result["data"])


class TestDashboard(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_dashboard_summary_success(self, mock_request):
		def side_effect(method, url, **kwargs):
			if url.endswith("/devices"):
				return _mock_response(200, [{"id": 1, "status": "online"}, {"id": 2, "status": "offline"}])
			if url.endswith("/groups"):
				return _mock_response(200, [{"id": 1, "name": "Fleet A"}])
			if url.endswith("/users"):
				return _mock_response(200, [{"id": 1, "name": "Admin"}])
			if url.endswith("/geofences"):
				return _mock_response(200, [{"id": 1, "name": "Warehouse"}])
			return _mock_response(404)

		mock_request.side_effect = side_effect
		result = dashboard.get_dashboard_summary()

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["devices_total"], 2)
		self.assertEqual(result["data"]["devices_online"], 1)
		self.assertEqual(result["data"]["groups_total"], 1)
		self.assertEqual(result["data"]["users_total"], 1)
		self.assertEqual(result["data"]["geofences_total"], 1)
		# Reports-dependent cards are honestly unavailable, not fabricated (Section 49).
		self.assertIsNone(result["data"]["events_today"])

	def test_dashboard_summary_not_configured(self):
		_set_settings(traccar_url="")
		result = dashboard.get_dashboard_summary()
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarConfigurationError")


class TestPhase2Permissions(FrappeTestCase):
	def setUp(self):
		_set_settings()

	def test_guest_cannot_call_get_devices(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_devices")()
		frappe.set_user("Administrator")
