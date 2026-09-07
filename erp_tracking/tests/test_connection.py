"""Connection test endpoint: success, auth failure, timeout and bad URL."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erp_tracking import api
from erp_tracking.integrations.traccar.exceptions import (
	TraccarAuthenticationError,
	TraccarConfigurationError,
	TraccarConnectionError,
	TraccarTimeoutError,
)
from erp_tracking.tests.test_auth import make_settings


class TestConnection(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		make_settings()

	def test_success(self):
		with patch(
			"erp_tracking.integrations.traccar.auth.TraccarAuth.authenticate",
			return_value={"email": "fleet@example.com"},
		), patch(
			"erp_tracking.integrations.traccar.server.get_server_info.raw", return_value={"version": "6.14.5"}
		):
			result = api.test_connection()

		self.assertTrue(result["success"])
		self.assertTrue(result["authenticated"])
		self.assertEqual(result["status_code"], 200)
		self.assertEqual(
			frappe.db.get_single_value("Traccar Settings", "connection_status"), "Connected"
		)

	def _failure(self, exception):
		with patch(
			"erp_tracking.integrations.traccar.auth.TraccarAuth.authenticate", side_effect=exception
		):
			return api.test_connection()

	def test_authentication_failure(self):
		result = self._failure(TraccarAuthenticationError())
		self.assertFalse(result["success"])
		self.assertFalse(result["authenticated"])
		self.assertEqual(result["status_code"], 401)
		self.assertEqual(frappe.db.get_single_value("Traccar Settings", "connection_status"), "Failed")

	def test_timeout(self):
		result = self._failure(TraccarTimeoutError())
		self.assertEqual(result["status_code"], 408)

	def test_server_unavailable(self):
		result = self._failure(TraccarConnectionError())
		self.assertEqual(result["status_code"], 503)

	def test_invalid_configuration(self):
		result = self._failure(TraccarConfigurationError())
		self.assertEqual(result["status_code"], 0)

	def test_invalid_url_rejected_on_save(self):
		settings = frappe.get_single("Traccar Settings")
		settings.traccar_url = "ftp://demo.traccar.org"
		with self.assertRaises(frappe.ValidationError):
			settings.save(ignore_permissions=True)
