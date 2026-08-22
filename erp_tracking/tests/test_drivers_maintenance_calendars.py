"""Phase 6 tests: Drivers, Maintenance, Calendars.

Run with:
    bench --site <site> run-tests --app erp_tracking \
        --module erp_tracking.tests.test_drivers_maintenance_calendars
"""

from __future__ import annotations

import base64
import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar import calendars, drivers, maintenance


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


class TestDrivers(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:drivers:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_driver(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "John Doe", "uniqueId": "JD001"})
		result = drivers.create_driver(name="John Doe", unique_id="JD001")
		self.assertTrue(result["success"])
		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/drivers"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_list_drivers_filtered_by_device(self, mock_request):
		mock_request.return_value = _mock_response(200, [{"id": 1, "name": "John Doe"}])
		drivers.get_drivers(device_id=10, refresh=True)
		called_params = mock_request.call_args.kwargs["params"]
		self.assertEqual(called_params["deviceId"], 10)


class TestMaintenance(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:maintenance:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_maintenance_item(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Oil Change", "type": "totalDistance", "start": 0, "period": 10000})
		result = maintenance.create_maintenance_item(name="Oil Change", type_="totalDistance", start=0, period=10000)
		self.assertTrue(result["success"])

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_maintenance_device_filter_passed_through(self, mock_request):
		mock_request.return_value = _mock_response(200, [])
		maintenance.get_maintenance_items(device_id=42, refresh=True)
		called_params = mock_request.call_args.kwargs["params"]
		self.assertEqual(called_params["deviceId"], 42)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_delete_maintenance_item(self, mock_request):
		resp = MagicMock(spec=requests.Response)
		resp.status_code = 204
		resp.headers = {}
		resp.content = b""
		mock_request.return_value = resp
		result = maintenance.delete_maintenance_item(1)
		self.assertTrue(result["success"])


class TestCalendars(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:calendars:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_calendar_encodes_ical_as_base64(self, mock_request):
		ical_text = "BEGIN:VCALENDAR\nEND:VCALENDAR"
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Business Hours"})

		calendars.create_calendar(name="Business Hours", ical_data=ical_text)

		sent_json = mock_request.call_args.kwargs["json"]
		self.assertEqual(sent_json["data"], base64.b64encode(ical_text.encode()).decode())

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_update_calendar_partial_fields(self, mock_request):
		mock_request.return_value = _mock_response(200, {"id": 1, "name": "Renamed"})
		calendars.update_calendar(1, name="Renamed")
		sent_json = mock_request.call_args.kwargs["json"]
		self.assertEqual(sent_json["name"], "Renamed")
		self.assertNotIn("data", sent_json)


class TestPhase6Permissions(FrappeTestCase):
	def setUp(self):
		_set_settings()

	def test_guest_cannot_view_drivers(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_drivers")()
		frappe.set_user("Administrator")

	def test_guest_cannot_view_calendars(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_calendars")()
		frappe.set_user("Administrator")

	def test_guest_cannot_create_maintenance_item(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.create_maintenance_item")(name="X", type_="totalDistance", start=0, period=1000)
		frappe.set_user("Administrator")
