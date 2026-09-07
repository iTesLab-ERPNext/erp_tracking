"""Export tests: CSV, XLSX, PDF and native Traccar passthrough."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erp_tracking import api, export as export_service
from erp_tracking.integrations.traccar.config import REPORT_CONFIG
from erp_tracking.tests.test_auth import make_settings

ROWS = [
	{"deviceName": "Truck 001", "distance": 15000, "duration": 3600000, "startTime": "2026-08-01T09:00:00Z"},
	{"deviceName": "Van 002", "distance": 8000, "duration": 1800000, "startTime": "2026-08-01T11:00:00Z"},
]
COLUMNS = REPORT_CONFIG["trips"]["columns"]


class TestExports(FrappeTestCase):
	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")

	def test_csv(self):
		content, mime, extension = export_service.build(ROWS, COLUMNS, "csv", "Trips")
		text = content.decode("utf-8-sig")
		self.assertEqual(extension, "csv")
		self.assertEqual(mime, "text/csv")
		self.assertIn("Truck 001", text)
		self.assertIn("Van 002", text)

	def test_xlsx(self):
		content, mime, extension = export_service.build(ROWS, COLUMNS, "xlsx", "Trips")
		self.assertEqual(extension, "xlsx")
		self.assertTrue(content[:2] == b"PK")  # zip container

	def test_pdf(self):
		content, mime, extension = export_service.build(ROWS, COLUMNS, "pdf", "Trips")
		self.assertEqual(extension, "pdf")
		self.assertTrue(content.startswith(b"%PDF"))

	def test_invalid_format_rejected(self):
		response = api.export_report("trips", frappe.as_json({"deviceId": [1], "from": "2026-08-01", "to": "2026-08-02"}), "exe")
		self.assertFalse(response["success"])

	def test_native_xlsx_is_preferred(self):
		"""Traccar's own /reports/trips/xlsx must be used, not a local render."""
		with patch(
			"erp_tracking.integrations.traccar.client.TraccarClient.request_raw",
			return_value=(b"PK-native", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
		) as raw:
			api.export_report(
				"trips", frappe.as_json({"deviceId": [1], "from": "2026-08-01", "to": "2026-08-19"}), "xlsx"
			)
		endpoint = raw.call_args[0][1]
		self.assertEqual(endpoint, "/reports/trips/xlsx")
		self.assertEqual(frappe.local.response.filecontent, b"PK-native")

	def test_positions_use_native_csv_endpoint(self):
		with patch(
			"erp_tracking.integrations.traccar.client.TraccarClient.request_raw",
			return_value=(b"id,latitude", "text/csv"),
		) as raw:
			api.export_positions(1, "2026-08-01", "2026-08-19", "csv")
		self.assertEqual(raw.call_args[0][1], "/positions/csv")

	def test_export_uses_current_filters(self):
		captured = {}

		def fake_get(endpoint, params=None, **kwargs):
			captured.update(params or {})
			return ROWS

		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", side_effect=fake_get):
			api.export_report(
				"trips",
				frappe.as_json({"deviceId": [7], "from": "2026-08-01", "to": "2026-08-19"}),
				"csv",
			)
		self.assertEqual(captured["deviceId"], [7])
		self.assertTrue(captured["from"].startswith("2026-08-01"))
