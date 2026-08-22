"""Phase 8 tests: Orders, Live Video (stream proxy).

Run with:
    bench --site <site> run-tests --app erp_tracking \
        --module erp_tracking.tests.test_orders_stream
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from erp_tracking.integrations.traccar import orders, stream
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


def _mock_text_response(status_code=200, text_body=""):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": "application/vnd.apple.mpegurl"}
	resp.content = text_body.encode()
	resp.text = text_body
	return resp


def _mock_binary_response(status_code=200, raw_bytes=b""):
	resp = MagicMock(spec=requests.Response)
	resp.status_code = status_code
	resp.headers = {"Content-Type": "video/mp2t"}
	resp.content = raw_bytes
	return resp


class TestOrders(FrappeTestCase):
	def setUp(self):
		_set_settings()
		frappe.cache().delete_keys("erp_tracking:orders:")

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_create_order(self, mock_request):
		mock_request.return_value = _mock_json_response(200, {"id": 1, "uniqueId": "ORD-001"})
		result = orders.create_order(unique_id="ORD-001", from_address="A St", to_address="B St")
		self.assertTrue(result["success"])
		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/orders"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_list_orders_exclude_attributes(self, mock_request):
		mock_request.return_value = _mock_json_response(200, [{"id": 1, "uniqueId": "ORD-001"}])
		orders.get_orders(exclude_attributes=True, refresh=True)
		called_params = mock_request.call_args.kwargs["params"]
		self.assertTrue(called_params["excludeAttributes"])

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_delete_order_invalidates_cache(self, mock_request):
		mock_request.return_value = _mock_json_response(200, [{"id": 1, "uniqueId": "ORD-001"}])
		orders.get_orders(refresh=True)
		self.assertIsNotNone(frappe.cache().get_value("erp_tracking:orders:None:None:False:None:None"))

		resp = MagicMock(spec=requests.Response)
		resp.status_code = 204
		resp.headers = {}
		resp.content = b""
		mock_request.return_value = resp
		orders.delete_order(1)

		self.assertIsNone(frappe.cache().get_value("erp_tracking:orders:None:None:False:None:None"))


class TestStreamProxy(FrappeTestCase):
	"""Section 35 / stream.py: the playlist must be rewritten so the
	browser never talks to Traccar directly, and segments must be
	proxied byte-for-byte.
	"""

	def setUp(self):
		_set_settings()

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_playlist_content_type_parsed_as_text_not_bytes(self, mock_request):
		"""Regression test: application/vnd.apple.mpegurl doesn't start
		with 'text/' and doesn't contain 'xml', so a naive content-type
		check would treat it as binary and hand stream.py raw bytes
		instead of a string, breaking the playlist line-rewriting. This
		proves TraccarClient._parse_body treats it as text."""
		mock_request.return_value = _mock_text_response(200, "#EXTM3U\n0.ts\n")
		rewritten = stream.get_playlist(device_id=1, channel=0)
		self.assertIsInstance(rewritten, str)
		self.assertIn("#EXTM3U", rewritten)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_playlist_segment_urls_rewritten_to_proxy(self, mock_request):
		original_playlist = "#EXTM3U\n#EXT-X-VERSION:3\n#EXTINF:10.0,\n0.ts\n#EXTINF:10.0,\n1.ts\n"
		mock_request.return_value = _mock_text_response(200, original_playlist)

		rewritten = stream.get_playlist(device_id=42, channel=0)
		rewritten_lines = rewritten.splitlines()

		self.assertIn("#EXTM3U", rewritten_lines)
		self.assertNotIn("0.ts", rewritten_lines)  # bare segment ref must be gone
		self.assertNotIn("1.ts", rewritten_lines)
		self.assertIn("erp_tracking.api.get_stream_segment?device_id=42&channel=0&index=0", rewritten)
		self.assertIn("erp_tracking.api.get_stream_segment?device_id=42&channel=0&index=1", rewritten)

		# Confirm the underlying Traccar call used the right endpoint.
		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/stream/42/0/live.m3u8"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_playlist_leaves_comment_and_tag_lines_untouched(self, mock_request):
		original_playlist = "#EXTM3U\n#EXT-X-TARGETDURATION:10\n0.ts\n"
		mock_request.return_value = _mock_text_response(200, original_playlist)

		rewritten = stream.get_playlist(device_id=1, channel=0)

		self.assertIn("#EXTM3U", rewritten)
		self.assertIn("#EXT-X-TARGETDURATION:10", rewritten)

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_get_segment_returns_raw_bytes(self, mock_request):
		fake_ts_bytes = b"\x47fake-mpeg-ts-segment-bytes"
		mock_request.return_value = _mock_binary_response(200, fake_ts_bytes)

		content = stream.get_segment(device_id=42, channel=0, index=3)

		self.assertIsInstance(content, bytes)
		self.assertEqual(content, fake_ts_bytes)
		called_url = mock_request.call_args.kwargs["url"]
		self.assertTrue(called_url.endswith("/stream/42/0/3.ts"))

	@patch("erp_tracking.integrations.traccar.client.requests.request")
	def test_stream_calls_require_normal_auth(self, mock_request):
		"""Unlike /server and /health (Phase 7), the stream endpoints have
		no security override in the spec - they must go through the
		normal authenticated path, sending real Authorization headers
		(server-side only; the browser never sees them - see stream.py)."""
		mock_request.return_value = _mock_text_response(200, "#EXTM3U\n")
		stream.get_playlist(device_id=1, channel=0)
		sent_headers = mock_request.call_args.kwargs["headers"]
		self.assertIn("Authorization", sent_headers)

	def test_get_segment_rejects_non_binary_response(self):
		with patch("erp_tracking.integrations.traccar.client.requests.request") as mock_request:
			mock_request.return_value = _mock_json_response(200, {"unexpected": "json"})
			with self.assertRaises(TraccarError):
				stream.get_segment(device_id=1, channel=0, index=0)


class TestPhase8Permissions(FrappeTestCase):
	def setUp(self):
		_set_settings()

	def test_guest_cannot_view_orders(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_orders")()
		frappe.set_user("Administrator")

	def test_guest_cannot_create_order(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.create_order")(unique_id="X")
		frappe.set_user("Administrator")

	def test_guest_cannot_fetch_stream_playlist(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			frappe.get_attr("erp_tracking.api.get_stream_playlist")(device_id=1)
		frappe.set_user("Administrator")
