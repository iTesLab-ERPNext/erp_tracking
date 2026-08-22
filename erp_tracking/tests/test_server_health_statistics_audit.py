"""Phase 7 tests: Server Information, Health, Statistics, Audit.

Run with:
    bench --site <site> run-tests --app erp_tracking \
        --module erp_tracking.tests.test_server_health_statistics_audit
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar import audit, server, statistics


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
	doc.flags.ignore_mandatory = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return doc


class _FakeSettings:
	"""Stand-in for TraccarSettingsData, used only to test the
	require_auth=False bypass without touching real encrypted-password
	storage (TraccarSettings.validate() legitimately refuses to save
	incomplete credentials via the normal Document flow, so this test
	needs a way to hand TraccarAuth a settings object directly instead).
	"""

	def __init__(self, url="https://demo.traccar.org/api", enabled=True, auth_type="Basic Auth", username="", password="", api_key=None, timeout=15, verify_ssl=True):
		self.url = url
		self.enabled = enabled
		self.auth_type = auth_type
		self.username = username
		self.password = password
		self.api_key = api_key
		self.timeout = timeout
		self.verify_ssl = verify_ssl


def _mock_json_response(status_code=200, json_body=None):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": "application/json"}
	resp.content = json.dumps(json_body).encode() if json_body is not None else b""
	resp.json.return_value = json_body
	return resp


def _mock_text_response(status_code=200, text_body="OK"):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": "text/plain"}
	resp.content = text_body.encode()
	resp.text = text_body
	return resp


class TestUnauthenticatedBypass(FrappeTestCase):
	"""Proves GET /server and GET /health work even with incomplete
	credentials, per the spec's `security: []` override - while a normal
	authenticated endpoint correctly still requires them.

	Uses a fake settings object (no real credentials configured) fed
	straight into TraccarClient, since TraccarSettings.validate() rightly
	refuses to persist incomplete credentials through the normal Document
	save flow - that refusal is correct app behavior, not something to work
	around at the DB layer.
	"""

	def _no_credentials_client(self):
		from erp_tracking.integrations.traccar.client import TraccarClient

		return TraccarClient(settings=_FakeSettings(username="", password=""))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_server_info_works_without_credentials(self, mock_request):
		mock_request.return_value = _mock_json_response(200, {"id": 1, "version": "6.14.5"})
		result = self._no_credentials_client().request_safe("GET", "server", require_auth=False)
		self.assertTrue(result["success"])

		# No Authorization header should have been sent.
		sent_headers = mock_request.call_args.kwargs["headers"]
		self.assertNotIn("Authorization", sent_headers)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_health_works_without_credentials(self, mock_request):
		mock_request.return_value = _mock_text_response(200, "OK")
		client = self._no_credentials_client()
		result = client.request_safe("GET", "health", require_auth=False, accept="text/plain")
		self.assertTrue(result["success"])

		sent_headers = mock_request.call_args.kwargs["headers"]
		self.assertNotIn("Authorization", sent_headers)

	def test_normal_endpoint_still_requires_credentials(self):
		"""Contrast case: a normal authenticated call (require_auth=True,
		the default) must still fail locally without credentials, proving
		the bypass is scoped to explicit require_auth=False calls only."""
		result = self._no_credentials_client().request_safe("GET", "devices")
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarConfigurationError")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_bypass_still_requires_url_and_enabled(self, mock_request):
		from erp_tracking.integrations.traccar.client import TraccarClient

		client = TraccarClient(settings=_FakeSettings(url="", username="", password=""))
		result = client.request_safe("GET", "health", require_auth=False, accept="text/plain")
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarConfigurationError")
		mock_request.assert_not_called()


class TestServerInfo(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_server_info(self, mock_request):
		mock_request.return_value = _mock_json_response(200, {"id": 1, "version": "6.14.5", "map": "osm"})
		result = server.get_server_info()
		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["version"], "6.14.5")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_update_server_info_requires_auth(self, mock_request):
		mock_request.return_value = _mock_json_response(200, {"id": 1, "announcement": "Maintenance tonight"})
		server.update_server_info(announcement="Maintenance tonight")
		sent_headers = mock_request.call_args.kwargs["headers"]
		self.assertIn("Authorization", sent_headers)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_timezones_cached(self, mock_request):
		mock_request.return_value = _mock_json_response(200, ["UTC", "America/New_York"])
		frappe.cache().delete_value("erp_tracking:timezones")
		result = server.get_timezones()
		self.assertTrue(result["success"])
		self.assertEqual(mock_request.call_count, 1)
		server.get_timezones()  # second call should hit cache
		self.assertEqual(mock_request.call_count, 1)


class TestStatistics(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_statistics(self, mock_request):
		mock_request.return_value = _mock_json_response(200, [{"captureTime": "2026-08-19T00:00:00Z", "activeDevices": 5}])
		result = statistics.get_statistics("2026-08-01", "2026-08-19")
		self.assertTrue(result["success"])

	def test_requires_dates(self):
		result = statistics.get_statistics(None, None)
		self.assertFalse(result["success"])
		self.assertEqual(result["status_code"], 400)


class TestAudit(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_audit_log(self, mock_request):
		mock_request.return_value = _mock_json_response(200, [{"id": 1, "actionType": "login", "userEmail": "admin@example.com"}])
		result = audit.get_audit_log("2026-08-01", "2026-08-19")
		self.assertTrue(result["success"])

	def test_requires_dates(self):
		result = audit.get_audit_log(None, "2026-08-19")
		self.assertFalse(result["success"])


class TestPhase7Permissions(FrappeTestCase):
	def setUp(self):
		_set_settings()

	def test_guest_cannot_view_server_info(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_server_info")()
		frappe.set_user("Administrator")

	def test_guest_cannot_view_audit_log(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_audit_log")(from_date="2026-08-01", to_date="2026-08-19")
		frappe.set_user("Administrator")

	def test_guest_cannot_view_statistics(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_statistics")(from_date="2026-08-01", to_date="2026-08-19")
		frappe.set_user("Administrator")

	def test_guest_cannot_update_server_info(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.update_server_info")(announcement="hi")
		frappe.set_user("Administrator")
