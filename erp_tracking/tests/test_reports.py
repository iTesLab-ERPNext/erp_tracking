"""Phase 4 tests: Reports engine (Trips, Stops, Summary, Events).

Run with:
    bench --site <site> run-tests --app erp_tracking \
        --module erp_tracking.tests.test_reports
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar import dashboard, reports
from erp_tracking.integrations.traccar.exceptions import TraccarError


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


def _mock_json_response(status_code=200, json_body=None):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": "application/json"}
	resp.content = json.dumps(json_body).encode() if json_body is not None else b""
	resp.json.return_value = json_body
	return resp


def _mock_binary_response(status_code=200, raw_bytes=b""):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
	resp.content = raw_bytes
	return resp


def _mock_no_content_response(status_code=204):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {}
	resp.content = b""
	return resp


class TestGenerateReport(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_generate_trips_report(self, mock_request):
		mock_request.return_value = _mock_json_response(200, [{"deviceId": 1, "distance": 1000}])
		result = reports.generate_report("trips", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19")
		self.assertTrue(result["success"])

		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/reports/trips"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_generate_summary_with_daily(self, mock_request):
		mock_request.return_value = _mock_json_response(200, [{"deviceId": 1, "distance": 500}])
		reports.generate_report("summary", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19", daily=True)
		called_params = mock_request.call_args.kwargs["params"]
		self.assertTrue(called_params["daily"])

	def test_daily_ignored_for_reports_that_dont_support_it(self):
		"""'daily' is only a Summary parameter per the spec - trips/stops/
		events must never send it, even if a caller passes it."""
		with patch("erp_tracking.integrations.traccar.client.requests.request") as mock_request:
			mock_request.return_value = _mock_json_response(200, [])
			reports.generate_report("trips", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19", daily=True)
			called_params = mock_request.call_args.kwargs["params"]
			self.assertNotIn("daily", called_params)

	def test_unknown_report_key_rejected(self):
		result = reports.generate_report("made_up_report", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19")
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarClientValidationError")

	def test_requires_device_or_group(self):
		result = reports.generate_report("trips", from_date="2026-08-01", to_date="2026-08-19")
		self.assertFalse(result["success"])

	def test_requires_dates(self):
		result = reports.generate_report("trips", device_ids=[1])
		self.assertFalse(result["success"])

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_events_report_type_filter(self, mock_request):
		mock_request.return_value = _mock_json_response(200, [])
		reports.generate_report(
			"events", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19", event_types=["deviceOnline", "alarm"]
		)
		called_params = mock_request.call_args.kwargs["params"]
		self.assertEqual(called_params["type"], ["deviceOnline", "alarm"])


class TestDownloadReport(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_download_xlsx_returns_raw_bytes_not_text(self, mock_request):
		"""Regression test for the binary-corruption bug: XLSX must come
		back as bytes, not a UTF-8-decoded string."""
		fake_xlsx_bytes = b"PK\x03\x04binary-spreadsheet-content"
		mock_request.return_value = _mock_binary_response(200, fake_xlsx_bytes)

		content = reports.download_report(
			"trips", "xlsx", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19"
		)
		self.assertIsInstance(content, bytes)
		self.assertEqual(content, fake_xlsx_bytes)

		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/reports/trips/xlsx"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_download_mail_returns_none_on_204(self, mock_request):
		mock_request.return_value = _mock_no_content_response(204)
		content = reports.download_report(
			"stops", "mail", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19"
		)
		self.assertIsNone(content)

	def test_download_rejects_unsupported_type(self):
		"""Section 50: never invent operations - only xlsx/mail exist for
		these report download endpoints, no csv/pdf."""
		with self.assertRaises(TraccarError):
			reports.download_report(
				"trips", "pdf", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19"
			)

	def test_download_unknown_report_rejected(self):
		with self.assertRaises(TraccarError):
			reports.download_report(
				"made_up", "xlsx", device_ids=[1], from_date="2026-08-01", to_date="2026-08-19"
			)


class TestDashboardTodayCounts(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_dashboard_computes_today_counts_for_small_fleet(self, mock_request):
		def side_effect(method, url, **kwargs):
			if url.endswith("/devices"):
				return _mock_json_response(200, [{"id": 1, "status": "online"}])
			if url.endswith("/groups"):
				return _mock_json_response(200, [])
			if url.endswith("/users"):
				return _mock_json_response(200, [])
			if url.endswith("/geofences"):
				return _mock_json_response(200, [])
			if url.endswith("/reports/events"):
				return _mock_json_response(200, [{"id": 1}, {"id": 2}])
			if url.endswith("/reports/trips"):
				return _mock_json_response(200, [{"id": 1}])
			if url.endswith("/reports/stops"):
				return _mock_json_response(200, [])
			return _mock_json_response(404)

		mock_request.side_effect = side_effect
		result = dashboard.get_dashboard_summary()

		self.assertTrue(result["success"])
		self.assertEqual(result["data"]["events_today"], 2)
		self.assertEqual(result["data"]["trips_today"], 1)
		self.assertEqual(result["data"]["stops_today"], 0)

	def test_dashboard_skips_today_counts_for_large_fleet(self):
		with patch("erp_tracking.integrations.traccar.dashboard.get_devices") as mock_get_devices, patch(
			"erp_tracking.integrations.traccar.dashboard.count_devices"
		) as mock_count_devices, patch("erp_tracking.integrations.traccar.dashboard.count_groups") as mock_count_groups, patch(
			"erp_tracking.integrations.traccar.dashboard.count_users"
		) as mock_count_users, patch(
			"erp_tracking.integrations.traccar.dashboard.get_geofences"
		) as mock_get_geofences:
			big_fleet = [{"id": i} for i in range(1, 100)]
			mock_get_devices.return_value = {"success": True, "data": big_fleet, "message": "OK", "status_code": 200, "error": None}
			mock_count_devices.return_value = {"success": True, "data": {"total": 99, "online": 99, "offline": 0}, "message": "OK", "status_code": 200, "error": None}
			mock_count_groups.return_value = {"success": True, "data": {"total": 0}, "message": "OK", "status_code": 200, "error": None}
			mock_count_users.return_value = {"success": True, "data": {"total": 0}, "message": "OK", "status_code": 200, "error": None}
			mock_get_geofences.return_value = {"success": True, "data": [], "message": "OK", "status_code": 200, "error": None}

			result = dashboard.get_dashboard_summary()
			self.assertTrue(result["success"])
			self.assertIsNone(result["data"]["events_today"])
			self.assertIsNone(result["data"]["trips_today"])
			self.assertIsNone(result["data"]["stops_today"])
