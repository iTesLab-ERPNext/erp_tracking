"""Authentication tests: Basic Auth, API Key, failures and missing credentials."""

import base64
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar.auth import TraccarAuth
from erp_tracking.integrations.traccar.exceptions import (
	TraccarAuthenticationError,
	TraccarConfigurationError,
	TraccarConnectionError,
	TraccarTimeoutError,
)


def make_settings(**overrides):
	settings = frappe.get_single("Traccar Settings")
	settings.traccar_url = overrides.get("traccar_url", "https://demo.traccar.org/api")
	settings.enabled = overrides.get("enabled", 1)
	settings.timeout = overrides.get("timeout", 10)
	settings.verify_ssl = overrides.get("verify_ssl", 1)
	settings.auth_type = overrides.get("auth_type", "Basic Auth")
	settings.username = overrides.get("username", "fleet@example.com")
	settings.password = overrides.get("password", "secret")
	settings.api_key = overrides.get("api_key", "token-123")
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)
	return frappe.get_doc("Traccar Settings")


def fake_response(status_code=200, payload=None, text=""):
	response = MagicMock()
	response.status_code = status_code
	response.json.return_value = payload if payload is not None else {}
	response.text = text
	response.content = b"{}"
	response.headers = {"Content-Type": "application/json"}
	return response


class TestTraccarAuth(FrappeTestCase):
	def test_basic_auth_header(self):
		auth = TraccarAuth(make_settings(auth_type="Basic Auth"))
		header = auth.get_auth_headers()["Authorization"]
		self.assertTrue(header.startswith("Basic "))
		decoded = base64.b64decode(header.split(" ")[1]).decode()
		self.assertEqual(decoded, "fleet@example.com:secret")

	def test_api_key_header(self):
		auth = TraccarAuth(make_settings(auth_type="API Key"))
		self.assertEqual(auth.get_auth_headers()["Authorization"], "Bearer token-123")

	@patch("erp_tracking.integrations.traccar.auth.requests.post")
	def test_basic_auth_success(self, post):
		post.return_value = fake_response(200, {"id": 1, "email": "fleet@example.com", "password": "x"})
		user = TraccarAuth(make_settings()).authenticate()
		self.assertEqual(user["email"], "fleet@example.com")
		# The sanitiser must strip the password out of the Traccar user record.
		self.assertNotIn("password", user)

	@patch("erp_tracking.integrations.traccar.auth.requests.post")
	def test_basic_auth_failure(self, post):
		post.return_value = fake_response(401)
		with self.assertRaises(TraccarAuthenticationError):
			TraccarAuth(make_settings()).authenticate()

	@patch("erp_tracking.integrations.traccar.auth.requests.get")
	def test_api_key_success(self, get):
		get.return_value = fake_response(200, {"id": 2, "email": "api@example.com"})
		user = TraccarAuth(make_settings(auth_type="API Key")).authenticate()
		self.assertEqual(user["email"], "api@example.com")

	@patch("erp_tracking.integrations.traccar.auth.requests.get")
	def test_api_key_failure(self, get):
		get.return_value = fake_response(403)
		with self.assertRaises(TraccarAuthenticationError):
			TraccarAuth(make_settings(auth_type="API Key")).authenticate()

	def test_missing_credentials(self):
		settings = make_settings()
		settings.username = None
		settings.password = None
		with self.assertRaises(TraccarConfigurationError):
			TraccarAuth(settings).get_auth_headers()

	def test_missing_url(self):
		settings = make_settings()
		settings.traccar_url = ""
		with self.assertRaises(TraccarConfigurationError):
			TraccarAuth(settings).validate_configuration()

	@patch("erp_tracking.integrations.traccar.auth.requests.post")
	def test_timeout(self, post):
		import requests

		post.side_effect = requests.Timeout("timed out")
		with self.assertRaises(TraccarTimeoutError):
			TraccarAuth(make_settings()).authenticate()

	@patch("erp_tracking.integrations.traccar.auth.requests.post")
	def test_server_unavailable(self, post):
		post.return_value = fake_response(503)
		with self.assertRaises(TraccarConnectionError):
			TraccarAuth(make_settings()).authenticate()
