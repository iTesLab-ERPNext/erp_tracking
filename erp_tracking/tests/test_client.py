"""Client tests: status mapping, path validation and log redaction."""

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar.client import TraccarClient
from erp_tracking.integrations.traccar.exceptions import (
	TraccarAPIError,
	TraccarAuthenticationError,
	TraccarConnectionError,
	TraccarNotFoundError,
	TraccarPermissionError,
	TraccarRateLimitError,
	TraccarTimeoutError,
)
from erp_tracking.integrations.traccar.utils import redact, validate_path
from erp_tracking.tests.test_auth import fake_response, make_settings


class TestTraccarClient(FrappeTestCase):
	def get_client(self):
		return TraccarClient(make_settings())

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_parses_json(self, request):
		request.return_value = fake_response(200, [{"id": 1, "name": "Truck 001"}])
		devices = self.get_client().get("/devices")
		self.assertEqual(devices[0]["name"], "Truck 001")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_status_code_mapping(self, request):
		cases = {
			400: TraccarAPIError,
			401: TraccarAuthenticationError,
			403: TraccarPermissionError,
			404: TraccarNotFoundError,
			408: TraccarTimeoutError,
			429: TraccarRateLimitError,
			500: TraccarConnectionError,
			502: TraccarConnectionError,
			503: TraccarConnectionError,
			504: TraccarTimeoutError,
		}
		for status, exception in cases.items():
			request.return_value = fake_response(status)
			with self.assertRaises(exception):
				self.get_client().get("/devices")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_timeout(self, request):
		import requests

		request.side_effect = requests.Timeout("slow")
		with self.assertRaises(TraccarTimeoutError):
			self.get_client().get("/devices")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_connection_error(self, request):
		import requests

		request.side_effect = requests.ConnectionError("refused")
		with self.assertRaises(TraccarConnectionError):
			self.get_client().get("/devices")

	def test_rejects_absolute_urls(self):
		"""The client must never become an open proxy."""
		for path in ("https://evil.example.com/steal", "//evil.example.com", "/../../etc/passwd", "devices"):
			with self.assertRaises(TraccarAPIError):
				validate_path(path)

	def test_accepts_documented_paths(self):
		for path in ("/devices", "/reports/trips", "/devices/12/accumulators"):
			self.assertEqual(validate_path(path), path)

	def test_redaction(self):
		self.assertEqual(redact({"password": "hunter2"})["password"], "***")
		self.assertNotIn("hunter2", redact("password=hunter2&x=1"))
		self.assertNotIn("abc123", redact("Authorization: Bearer abc123"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_logs_never_contain_secrets(self, request):
		request.return_value = fake_response(200, [])
		with patch.object(TraccarClient, "_log") as log:
			self.get_client().get("/devices")
			args = log.call_args[0]
			self.assertNotIn("secret", str(args))
