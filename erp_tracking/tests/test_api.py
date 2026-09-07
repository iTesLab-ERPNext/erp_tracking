"""API tests: devices, positions, reports, filters and the response envelope."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erp_tracking import api
from erp_tracking.integrations.traccar.exceptions import TraccarAuthenticationError
from erp_tracking.tests.test_auth import make_settings

DEVICES = [
	{"id": 1, "name": "Truck 001", "uniqueId": "3333", "status": "online", "groupId": 2},
	{"id": 2, "name": "Van 002", "uniqueId": "4444", "status": "offline", "groupId": 2},
]

POSITIONS = [
	{"id": 10, "deviceId": 1, "latitude": 36.8, "longitude": 10.18, "speed": 12, "fixTime": "2026-08-01T09:00:00Z"},
	{"id": 11, "deviceId": 2, "latitude": 36.9, "longitude": 10.2, "speed": 0, "fixTime": "2026-08-01T09:05:00Z"},
]

TRIPS = [
	{"deviceId": 1, "deviceName": "Truck 001", "distance": 15000, "duration": 3600000, "maxSpeed": 40, "averageSpeed": 22, "spentFuel": 4.2},
]


class TestTrackingApi(FrappeTestCase):
	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")
		frappe.cache().delete_keys("erp_tracking")

	def test_envelope_shape(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", return_value=DEVICES):
			response = api.get_devices()
		for key in ("success", "data", "message", "status_code", "error"):
			self.assertIn(key, response)
		self.assertTrue(response["success"])

	def test_list_devices(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", return_value=DEVICES):
			response = api.get_devices()
		self.assertEqual(len(response["data"]["items"]), 2)
		self.assertEqual(response["data"]["items"][0]["name"], "Truck 001")

	def test_get_device(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", return_value=DEVICES[0]):
			response = api.get_device(1)
		self.assertEqual(response["data"]["uniqueId"], "3333")

	def test_api_error_becomes_envelope(self):
		with patch(
			"erp_tracking.integrations.traccar.client.TraccarClient.get",
			side_effect=TraccarAuthenticationError(),
		):
			response = api.get_devices()
		self.assertFalse(response["success"])
		self.assertEqual(response["status_code"], 401)
		self.assertIsNone(response["data"])

	def test_live_positions_filtered_by_device(self):
		def fake_get(endpoint, params=None, **kwargs):
			return POSITIONS if endpoint == "/positions" else DEVICES

		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", side_effect=fake_get):
			response = api.get_live_positions(device_ids="1")
		self.assertEqual(len(response["data"]["items"]), 1)
		self.assertEqual(response["data"]["items"][0]["deviceName"], "Truck 001")

	def test_position_history_sends_date_filters(self):
		captured = {}

		def fake_get(endpoint, params=None, **kwargs):
			if endpoint == "/positions":
				captured.update(params or {})
				return POSITIONS
			return DEVICES

		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", side_effect=fake_get):
			api.get_position_history(1, "2026-08-01", "2026-08-19")

		self.assertEqual(captured["deviceId"], 1)
		self.assertTrue(captured["from"].endswith("Z"))
		self.assertTrue(captured["to"].endswith("Z"))

	def test_report_requires_device_or_group(self):
		response = api.run_report("trips", frappe.as_json({"from": "2026-08-01", "to": "2026-08-19"}))
		self.assertFalse(response["success"])

	def test_reports_run(self):
		for report, payload in (
			("trips", TRIPS),
			("stops", [{"deviceId": 1, "duration": 600000, "address": "Tunis"}]),
			("summary", [{"deviceId": 1, "deviceName": "Truck 001", "distance": 1000, "engineHours": 3600000}]),
			("events", [{"id": 5, "deviceId": 1, "type": "deviceOverspeed", "eventTime": "2026-08-01T10:00:00Z"}]),
			("route", POSITIONS),
		):
			def fake_get(endpoint, params=None, **kwargs):
				return DEVICES if endpoint == "/devices" else payload

			with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", side_effect=fake_get):
				response = api.run_report(
					report,
					frappe.as_json({"deviceId": [1], "from": "2026-08-01", "to": "2026-08-19"}),
				)
			self.assertTrue(response["success"], msg=report)
			self.assertEqual(response["data"]["report"], report)
			self.assertTrue(response["data"]["columns"])

	def test_route_report_returns_track(self):
		def fake_get(endpoint, params=None, **kwargs):
			return DEVICES if endpoint == "/devices" else POSITIONS

		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", side_effect=fake_get):
			response = api.run_report(
				"route", frappe.as_json({"deviceId": [1], "from": "2026-08-01", "to": "2026-08-19"})
			)
		self.assertEqual(len(response["data"]["track"]), 2)
