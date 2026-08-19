"""Phase 1 tests: authentication, connection handling, and secret safety.

Run with:
    bench --site <site> run-tests --app erp_tracking --module erp_tracking.tests.test_traccar_settings
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar.auth import TraccarAuth
from erp_tracking.integrations.traccar.client import TraccarClient
from erp_tracking.integrations.traccar.exceptions import (
	TraccarAuthenticationError,
	TraccarConfigurationError,
	TraccarConnectionError,
	TraccarTimeoutError,
)


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
		api_key=None,
	)
	defaults.update(kwargs)
	for field, value in defaults.items():
		doc.set(field, value)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc


def _mock_response(status_code=200, json_body=None, text_body="", content_type="application/json"):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": content_type}
	resp.content = json.dumps(json_body).encode() if json_body is not None else b""
	resp.json.return_value = json_body
	resp.text = text_body
	return resp


class TestAuthentication(FrappeTestCase):
	def test_basic_auth_success(self):
		_set_settings(auth_type="Basic Auth", username="admin", password="secret-password")
		headers = TraccarAuth().get_auth_headers()
		self.assertIn("Authorization", headers)
		self.assertTrue(headers["Authorization"].startswith("Basic "))

	def test_basic_auth_missing_credentials_fails(self):
		_set_settings(auth_type="Basic Auth", username="", password="")
		with self.assertRaises(TraccarConfigurationError):
			TraccarAuth().get_auth_headers()

	def test_api_key_success(self):
		_set_settings(auth_type="API Key", api_key="abc123token")
		headers = TraccarAuth().get_auth_headers()
		self.assertEqual(headers["Authorization"], "Bearer abc123token")

	def test_api_key_missing_fails(self):
		_set_settings(auth_type="API Key", api_key="")
		with self.assertRaises(TraccarConfigurationError):
			TraccarAuth().get_auth_headers()

	def test_missing_url_fails(self):
		_set_settings(traccar_url="")
		with self.assertRaises(TraccarConfigurationError):
			TraccarAuth().authenticate()

	def test_disabled_integration_fails(self):
		_set_settings(enabled=0)
		with self.assertRaises(TraccarConfigurationError):
			TraccarAuth().authenticate()


class TestConnection(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_connection_success(self, mock_request):
		mock_request.return_value = _mock_response(200, json_body={"id": 1, "email": "admin@example.com"})
		result = TraccarClient().request_safe("GET", "session")
		self.assertTrue(result["success"])
		self.assertEqual(result["status_code"], 200)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_connection_timeout(self, mock_request):
		mock_request.side_effect = requests.exceptions.Timeout()
		result = TraccarClient().request_safe("GET", "session")
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarTimeoutError")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_server_unavailable(self, mock_request):
		mock_request.side_effect = requests.exceptions.ConnectionError()
		result = TraccarClient().request_safe("GET", "session")
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarConnectionError")

	def test_invalid_configuration(self):
		_set_settings(traccar_url="")
		result = TraccarClient().request_safe("GET", "session")
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarConfigurationError")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_authentication_failure(self, mock_request):
		mock_request.return_value = _mock_response(401)
		result = TraccarClient().request_safe("GET", "session")
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarAuthenticationError")
		self.assertEqual(result["status_code"], 401)


class TestDevicesClientCalls(FrappeTestCase):
	"""Smoke-tests the generic client against the /devices endpoint. Full
	Devices feature coverage (list, get, filters) lands with devices.py
	in Phase 2, per the brief's own phase ordering.
	"""

	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_list_devices(self, mock_request):
		mock_request.return_value = _mock_response(
			200, json_body=[{"id": 1, "name": "Truck 001", "uniqueId": "123456"}]
		)
		result = TraccarClient().request_safe("GET", "devices")
		self.assertTrue(result["success"])
		self.assertEqual(result["data"][0]["name"], "Truck 001")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_devices_api_error(self, mock_request):
		mock_request.return_value = _mock_response(500)
		result = TraccarClient().request_safe("GET", "devices")
		self.assertFalse(result["success"])
		self.assertEqual(result["status_code"], 500)


class TestSecuritySecretsNeverExposed(FrappeTestCase):
	def setUp(self):
		_set_settings(auth_type="API Key", api_key="super-secret-key")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_secrets_never_in_response(self, mock_request):
		mock_request.return_value = _mock_response(200, json_body={"ok": True})
		result = TraccarClient().request_safe("GET", "session")
		dumped = json.dumps(result)
		self.assertNotIn("super-secret-key", dumped)

	def test_get_connection_status_excludes_secrets(self):
		from erp_tracking.api import get_connection_status

		result = get_connection_status()
		dumped = json.dumps(result, default=str)
		self.assertNotIn("super-secret-key", dumped)

	def test_unauthorized_role_cannot_test_connection(self):
		from erp_tracking.erp_tracking.doctype.traccar_settings.traccar_settings import (
			test_connection,
		)

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			test_connection()
		frappe.set_user("Administrator")
