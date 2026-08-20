"""Phase 3 tests: Positions, Route.

Run with:
    bench --site <site> run-tests --app erp_tracking \
        --module erp_tracking.tests.test_positions_route
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar import positions, route
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


def _mock_text_response(status_code=200, text_body="", content_type="text/csv"):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": content_type}
	resp.content = text_body.encode()
	resp.text = text_body
	return resp


class TestLivePositions(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_key("erp_tracking:positions:live")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_live_positions(self, mock_request):
		mock_request.return_value = _mock_json_response(
			200, [{"id": 1, "deviceId": 10, "latitude": 1.0, "longitude": 2.0}]
		)
		result = positions.get_live_positions(refresh=True)
		self.assertTrue(result["success"])
		self.assertEqual(len(result["data"]), 1)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_live_positions_filtered_by_device(self, mock_request):
		mock_request.return_value = _mock_json_response(
			200,
			[
				{"id": 1, "deviceId": 10, "latitude": 1.0, "longitude": 2.0},
				{"id": 2, "deviceId": 20, "latitude": 3.0, "longitude": 4.0},
			],
		)
		result = positions.get_live_positions(device_id=10, refresh=True)
		self.assertTrue(result["success"])
		self.assertEqual(len(result["data"]), 1)
		self.assertEqual(result["data"][0]["deviceId"], 10)


class TestPositionHistory(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_position_history(self, mock_request):
		mock_request.return_value = _mock_json_response(200, [{"id": 1, "deviceId": 10}])
		result = positions.get_position_history(10, "2026-08-01 00:00:00", "2026-08-19 00:00:00")
		self.assertTrue(result["success"])

	def test_position_history_requires_device(self):
		result = positions.get_position_history(None, "2026-08-01", "2026-08-19")
		self.assertFalse(result["success"])
		self.assertEqual(result["status_code"], 400)

	def test_position_history_requires_dates(self):
		result = positions.get_position_history(10, None, None)
		self.assertFalse(result["success"])


class TestPositionExports(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_export_csv_uses_native_endpoint(self, mock_request):
		mock_request.return_value = _mock_text_response(200, "deviceId,time\n10,2026-08-19", "text/csv")
		content = positions.export_positions_csv(10, "2026-08-01", "2026-08-19")
		self.assertIn("deviceId", content)

		# Confirm it hit /positions/csv, not a hand-rolled CSV endpoint.
		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/positions/csv"))

	def test_export_requires_all_params(self):
		with self.assertRaises(TraccarError):
			positions.export_positions_csv(None, None, None)


class TestRoute(FrappeTestCase):
	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_route_by_device(self, mock_request):
		mock_request.return_value = _mock_json_response(
			200, [{"id": 1, "deviceId": 10, "latitude": 1.0, "longitude": 2.0}]
		)
		result = route.get_route(device_ids=[10], from_date="2026-08-01", to_date="2026-08-19")
		self.assertTrue(result["success"])

		called_params = mock_request.call_args.kwargs["params"]
		self.assertEqual(called_params["deviceId"], [10])

	def test_get_route_requires_device_or_group(self):
		result = route.get_route(from_date="2026-08-01", to_date="2026-08-19")
		self.assertFalse(result["success"])
		self.assertEqual(result["error"], "TraccarClientValidationError")

	def test_get_route_requires_dates(self):
		result = route.get_route(device_ids=[10])
		self.assertFalse(result["success"])
