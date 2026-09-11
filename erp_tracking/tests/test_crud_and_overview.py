"""Tests for the CRUD additions (devices, groups, users, calendars, drivers)
and the new Reports > Overview / combined-report endpoints.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from erp_tracking import api
from erp_tracking.permissions import ROLE_USER, ROLE_VIEWER
from erp_tracking.tests.test_auth import make_settings
from erp_tracking.tests.test_security import make_user

DEVICE = {"id": 1, "name": "Truck 001", "uniqueId": "3333", "status": "online", "groupId": 2}
GROUP = {"id": 2, "name": "Fleet A", "groupId": None}
DRIVER = {"id": 3, "name": "Jane Doe", "uniqueId": "D-001"}
CALENDAR_RAW = {"id": 4, "name": "Business Hours", "data": "QkVHSU46VkNBTEVOREFS"}  # b64 "BEGIN:VCALENDAR"
USER_ROW = {"id": 5, "name": "Fleet Admin", "email": "fleet@example.com", "password": "hash", "administrator": True}


class TestDeviceCrud(FrappeTestCase):
	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")
		frappe.cache().delete_keys("erp_tracking")

	def test_save_device_create(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.post", return_value=DEVICE):
			response = api.save_device(frappe.as_json({"name": "Truck 001", "uniqueId": "3333"}))
		self.assertTrue(response["success"])
		self.assertEqual(response["data"]["uniqueId"], "3333")

	def test_save_device_update(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.put", return_value=DEVICE):
			response = api.save_device(frappe.as_json({"name": "Truck 001", "uniqueId": "3333"}), device_id=1)
		self.assertTrue(response["success"])

	def test_save_device_requires_name_and_unique_id(self):
		response = api.save_device(frappe.as_json({"name": "Truck 001"}))
		self.assertFalse(response["success"])
		self.assertEqual(response["status_code"], 400)

	def test_delete_device(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.delete", return_value=None):
			response = api.delete_device(1)
		self.assertTrue(response["success"])

	def test_user_role_cannot_write_devices(self):
		frappe.set_user(make_user("erpt-crud-user@example.com", [ROLE_USER]))
		with self.assertRaises(frappe.PermissionError):
			api.save_device(frappe.as_json({"name": "X", "uniqueId": "Y"}))
		with self.assertRaises(frappe.PermissionError):
			api.delete_device(1)


class TestGroupCrud(FrappeTestCase):
	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")
		frappe.cache().delete_keys("erp_tracking")

	def test_save_group_create(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.post", return_value=GROUP):
			response = api.save_group(frappe.as_json({"name": "Fleet A"}))
		self.assertTrue(response["success"])

	def test_save_group_requires_name(self):
		response = api.save_group(frappe.as_json({}))
		self.assertFalse(response["success"])

	def test_delete_group(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.delete", return_value=None):
			response = api.delete_group(2)
		self.assertTrue(response["success"])

	def test_viewer_cannot_write_groups(self):
		frappe.set_user(make_user("erpt-crud-viewer@example.com", [ROLE_VIEWER]))
		with self.assertRaises(frappe.PermissionError):
			api.save_group(frappe.as_json({"name": "X"}))


class TestDriverCrudAlreadyWired(FrappeTestCase):
	"""Drivers already had full backend + api.py CRUD before this change -
	these just confirm nothing regressed while other modules were touched.
	"""

	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")
		frappe.cache().delete_keys("erp_tracking")

	def test_save_driver_still_works(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.post", return_value=DRIVER):
			response = api.save_driver(frappe.as_json({"name": "Jane Doe", "uniqueId": "D-001"}))
		self.assertTrue(response["success"])

	def test_delete_driver_still_works(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.delete", return_value=None):
			response = api.delete_driver(3)
		self.assertTrue(response["success"])


class TestUserCrud(FrappeTestCase):
	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")
		frappe.cache().delete_keys("erp_tracking")

	def test_create_user_requires_password(self):
		response = api.save_user(frappe.as_json({"name": "Fleet Admin", "email": "fleet@example.com"}))
		self.assertFalse(response["success"])

	def test_create_user_sends_password_but_never_returns_it(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.post", return_value=USER_ROW) as mock_post:
			response = api.save_user(
				frappe.as_json({"name": "Fleet Admin", "email": "fleet@example.com", "password": "s3cret!"})
			)
		self.assertTrue(response["success"])
		self.assertNotIn("password", response["data"])
		sent_payload = mock_post.call_args.kwargs.get("json_body") or mock_post.call_args[0][1]
		self.assertEqual(sent_payload["password"], "s3cret!")

	def test_update_user_without_password_does_not_send_one(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.put", return_value=USER_ROW) as mock_put:
			api.save_user(frappe.as_json({"name": "Fleet Admin", "email": "fleet@example.com"}), user_id=5)
		sent_payload = mock_put.call_args.kwargs.get("json_body") or mock_put.call_args[0][1]
		self.assertNotIn("password", sent_payload)

	def test_update_user_with_new_password_sends_it(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.put", return_value=USER_ROW) as mock_put:
			api.save_user(
				frappe.as_json({"name": "Fleet Admin", "email": "fleet@example.com", "password": "new-pass!"}),
				user_id=5,
			)
		sent_payload = mock_put.call_args.kwargs.get("json_body") or mock_put.call_args[0][1]
		self.assertEqual(sent_payload["password"], "new-pass!")

	def test_manager_role_cannot_manage_users(self):
		# Users are gated with ensure_admin(), same as get_users() already was.
		frappe.set_user(make_user("erpt-crud-user2@example.com", [ROLE_USER]))
		with self.assertRaises(frappe.PermissionError):
			api.save_user(frappe.as_json({"name": "X", "email": "x@example.com", "password": "pw"}))
		with self.assertRaises(frappe.PermissionError):
			api.delete_user(5)


class TestCalendarCrud(FrappeTestCase):
	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")
		frappe.cache().delete_keys("erp_tracking")

	def test_get_calendar_decodes_ical_text(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", return_value=dict(CALENDAR_RAW)):
			response = api.get_calendar(4)
		self.assertTrue(response["success"])
		self.assertEqual(response["data"]["ical_text"], "BEGIN:VCALENDAR")
		self.assertNotIn("data", response["data"])

	def test_create_calendar_encodes_ical_text(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.post", return_value=dict(CALENDAR_RAW)) as mock_post:
			response = api.save_calendar(
				frappe.as_json({"name": "Business Hours", "ical_text": "BEGIN:VCALENDAR\nEND:VCALENDAR"})
			)
		self.assertTrue(response["success"])
		sent_payload = mock_post.call_args.kwargs.get("json_body") or mock_post.call_args[0][1]
		self.assertNotIn("ical_text", sent_payload)
		self.assertIn("data", sent_payload)

	def test_save_calendar_requires_schedule(self):
		response = api.save_calendar(frappe.as_json({"name": "Business Hours"}))
		self.assertFalse(response["success"])

	def test_delete_calendar(self):
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.delete", return_value=None):
			response = api.delete_calendar(4)
		self.assertTrue(response["success"])

	def test_viewer_can_read_but_not_write_calendars(self):
		frappe.set_user(make_user("erpt-crud-viewer2@example.com", [ROLE_VIEWER]))
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get", return_value=[]):
			response = api.get_list("calendars")
		self.assertTrue(response["success"])
		with self.assertRaises(frappe.PermissionError):
			api.save_calendar(frappe.as_json({"name": "X", "ical_text": "BEGIN:VCALENDAR\nEND:VCALENDAR"}))


class TestCombinedReport(FrappeTestCase):
	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")
		frappe.cache().delete_keys("erp_tracking")

	def test_combined_report_requires_device_or_group(self):
		response = api.get_combined_report(frappe.as_json({"from": "2026-08-01", "to": "2026-08-02"}))
		self.assertFalse(response["success"])
		self.assertEqual(response["status_code"], 400)

	def test_combined_report_enriches_device_name(self):
		combined_rows = [{"deviceId": 1, "route": [[10.18, 36.8]], "events": [{"id": 1}], "positions": []}]
		with patch("erp_tracking.integrations.traccar.client.TraccarClient.get") as mock_get:
			mock_get.side_effect = [combined_rows, [DEVICE]]
			response = api.get_combined_report(
				frappe.as_json({"deviceId": [1], "from": "2026-08-01", "to": "2026-08-02"})
			)
		self.assertTrue(response["success"])
		item = response["data"]["items"][0]
		self.assertEqual(item["deviceName"], "Truck 001")
		self.assertEqual(item["eventCount"], 1)


class TestFleetOverview(FrappeTestCase):
	def setUp(self):
		make_settings()
		frappe.set_user("Administrator")
		frappe.cache().delete_keys("erp_tracking")

	def test_overview_empty_when_no_devices(self):
		with patch("erp_tracking.integrations.traccar.devices.device_map", return_value={}):
			response = api.get_fleet_overview("2026-08-01", "2026-08-02")
		self.assertTrue(response["success"])
		self.assertTrue(response["data"]["empty"])
		self.assertEqual(response["data"]["kpi"], [])

	def test_overview_builds_kpis_and_breakdowns(self):
		trips = [
			{"deviceId": 1, "deviceName": "Truck 001", "distance": 15000, "duration": 3600000, "driverName": "Jane", "startTime": "2026-08-01T10:00:00Z"},
		]
		summary = [{"deviceId": 1, "deviceName": "Truck 001", "distance": 15000}]

		with patch("erp_tracking.integrations.traccar.devices.device_map", return_value={1: DEVICE}), patch(
			"erp_tracking.integrations.traccar.groups.group_choices", return_value=[{"value": 2, "label": "Fleet A"}]
		), patch("erp_tracking.integrations.traccar.reports.fetch_report") as mock_fetch:

			def fake_fetch(name, filters):
				return {"trips": trips, "summary": summary, "events": []}[name]

			mock_fetch.side_effect = fake_fetch
			response = api.get_fleet_overview("2026-08-01", "2026-08-02", device_ids="[1]")

		self.assertTrue(response["success"])
		data = response["data"]
		self.assertFalse(data["empty"])
		self.assertEqual(len(data["kpi"]), 6)
		self.assertEqual(data["by_device"][0]["label"], "Truck 001")
		self.assertEqual(data["by_driver"][0]["label"], "Jane")
		self.assertEqual(data["by_group"][0]["label"], "Fleet A")
		self.assertEqual(data["trips_per_day"]["labels"], ["2026-08-01"])
		self.assertEqual(data["trips_per_day"]["values"], [1])

	def test_devices_report_export_endpoint_exists(self):
		with patch(
			"erp_tracking.integrations.traccar.reports.fetch_devices_report",
			return_value=(b"binary-xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
		):
			# export_devices_report streams a download via frappe.response
			# rather than returning an envelope on success; it should not
			# raise for a well-formed, mocked download.
			api.export_devices_report()
