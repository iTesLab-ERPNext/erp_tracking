"""Live video (HLS).

The HLS endpoints are authenticated.  Handing the browser a Traccar session
token would put a credential in the DOM, which the security requirements
forbid, so the playlist and its segments are relayed by the server and the
playlist URIs are rewritten to point back at Frappe.  Only the bytes travel
through ERPNext - no credential ever reaches the client.

The feature stays off until ``enable_live_video`` is ticked in Traccar
Settings.
"""

import re

from frappe import _
from frappe.utils import cint

from erp_tracking.integrations.traccar.auth import get_settings
from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.exceptions import TraccarConfigurationError

SEGMENT_PATTERN = re.compile(r"^(?!#)(\S*?)(\d+)\.ts\s*$", re.MULTILINE)
PLAYLIST_MIME = "application/vnd.apple.mpegurl"
SEGMENT_MIME = "video/mp2t"


def ensure_enabled():
	settings = get_settings()
	if not cint(settings.get("enable_live_video")):
		raise TraccarConfigurationError(_("Live video is disabled in Traccar Settings."))


def fetch_playlist(device_id, channel, rewrite_base):
	"""Return the HLS playlist with segment URIs pointing back at Frappe."""
	ensure_enabled()
	endpoint = TRACCAR_ENDPOINTS["stream_playlist"].format(
		deviceId=cint(device_id), channel=cint(channel)
	)
	content, _mime = get_client().request_raw("GET", endpoint, accept=PLAYLIST_MIME)
	playlist = content.decode("utf-8", errors="ignore")

	def _rewrite(match):
		index = match.group(2)
		return f"{rewrite_base}&index={index}"

	return SEGMENT_PATTERN.sub(_rewrite, playlist)


def fetch_segment(device_id, channel, index):
	ensure_enabled()
	endpoint = TRACCAR_ENDPOINTS["stream_segment"].format(
		deviceId=cint(device_id), channel=cint(channel), index=cint(index)
	)
	content, _mime = get_client().request_raw("GET", endpoint, accept=SEGMENT_MIME)
	return content
