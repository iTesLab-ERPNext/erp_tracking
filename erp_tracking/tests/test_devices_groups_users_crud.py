"""Tests for Devices/Groups/Users write operations (create/update/delete).

Run with:
    bench --site <site> run-tests --app erp_tracking \
        --module erp_tracking.tests.test_devices_groups_users_crud
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar import devices, groups, users


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


def _mock_no_content():
	resp = MagicMock(spec=requests.Response)
	resp.status_code = 204
	resp.headers = {}
	resp.content = b""
	return resp


class TestDeviceCRUD(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:devices:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_device(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Truck 001", "uniqueId": "TR001"})
		result = devices.create_device(name="Truck 001", unique_id="TR001")
		self.assertTrue(result["success"])
		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/devices"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_update_device(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Truck 001 Renamed"})
		result = devices.update_device(1, name="Truck 001 Renamed")
		self.assertTrue(result["success"])
		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/devices/1"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_delete_device_invalidates_cache(self, mock_request):
		mock_request.return_value = _mock_response(200, [{"id": 1, "name": "Truck 001"}])
		devices.get_devices(refresh=True)
		self.assertIsNotNone(frappe.cache().get_value("erp_tracking:devices:None:None:None"))

		mock_request.return_value = _mock_no_content()
		devices.delete_device(1)
		self.assertIsNone(frappe.cache().get_value("erp_tracking:devices:None:None:None"))


class TestGroupCRUD(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:groups:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_group(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Fleet A"})
		result = groups.create_group(name="Fleet A")
		self.assertTrue(result["success"])

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_group_with_parent(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 2, "name": "Sub Fleet", "groupId": 1})
		groups.create_group(name="Sub Fleet", group_id=1)
		sent_json = mock_request.call_args.kwargs["json"]
		self.assertEqual(sent_json["groupId"], 1)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_delete_group(self, mock_request):
		mock_request.return_value = _mock_no_content()
		result = groups.delete_group(1)
		self.assertTrue(result["success"])


class TestUserCRUD(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:users:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_user_sends_password(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Jane", "email": "jane@example.com"})
		users.create_user(name="Jane", email="jane@example.com", password="s3cret!")
		sent_json = mock_request.call_args.kwargs["json"]
		self.assertEqual(sent_json["password"], "s3cret!")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_user_response_never_leaks_password(self, mock_request):
		# Even if a (misconfigured) server echoed the password back, the
		# response must never contain it - same redaction as get_user/get_users.
		mock_request.return_value = _mock_response(
			200, {"id": 1, "name": "Jane", "email": "jane@example.com", "password": "s3cret!"}
		)
		result = users.create_user(name="Jane", email="jane@example.com", password="s3cret!")
		self.assertNotIn("password", result["data"])
		self.assertNotIn("s3cret!", json.dumps(result))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_update_user_without_password_does_not_send_one(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Jane Updated"})
		users.update_user(1, password=None, name="Jane Updated")
		sent_json = mock_request.call_args.kwargs["json"]
		self.assertNotIn("password", sent_json)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_update_user_with_new_password_sends_it(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Jane"})
		users.update_user(1, password="new-pass!", name="Jane")
		sent_json = mock_request.call_args.kwargs["json"]
		self.assertEqual(sent_json["password"], "new-pass!")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_delete_user(self, mock_request):
		mock_request.return_value = _mock_no_content()
		result = users.delete_user(1)
		self.assertTrue(result["success"])


class TestDevicesGroupsUsersWritePermissions(FrappeTestCase):
	def setUp(self):
		_set_settings()

	def test_guest_cannot_create_device(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.create_device")(name="X", unique_id="Y")
		frappe.set_user("Administrator")

	def test_guest_cannot_create_group(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.create_group")(name="X")
		frappe.set_user("Administrator")

	def test_guest_cannot_create_user(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.create_user")(name="X", email="x@example.com", password="pw")
		frappe.set_user("Administrator")
