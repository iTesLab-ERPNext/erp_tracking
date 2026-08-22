"""Live Video / Stream feature module (Section 35).

The spec defines two endpoints for HLS playback:
  GET /stream/{deviceId}/{channel}/live.m3u8   - the HLS playlist
  GET /stream/{deviceId}/{channel}/{index}.ts  - individual video segments

Both require the normal BasicAuth/ApiKey authentication - no security
override in the spec. That creates a direct conflict between two
requirements in the brief:

  - Section 35: "Do not proxy video through ERPNext unnecessarily."
  - Section 41 (hard security requirement): "The frontend must never
    receive passwords, API keys, tokens or Authorization headers."

Traccar's own documented workaround for browser players that can't set a
custom Authorization header is to append a short-lived session token as a
query string (`?token=...`, from POST /session/token). But Section 41
explicitly lists "tokens" alongside passwords and API keys as things the
frontend must never receive - it doesn't carve out an exception for
short-lived ones. That workaround is therefore not available here without
breaking a hard "Never" requirement.

Given the conflict, this module proxies the stream through ERPNext:
fetching the playlist and each segment server-side (real credentials touch
only this server-side request, exactly like every other endpoint in the
app), and rewriting the playlist's segment references to point back at
this app's own whitelisted segment endpoint instead of Traccar's directly.
The browser's HLS player only ever talks to ERPNext over the user's
already-authenticated Frappe session - no Traccar credentials or tokens
ever reach it. This is "necessary" proxying in the sense Section 35
allows for (the only alternative violates Section 41), not the general
video-relaying Section 35 warns against.
"""

from __future__ import annotations

import re

from .client import TraccarClient
from .exceptions import TraccarError

# Matches a bare "<index>.ts" line in the HLS playlist - the segment
# reference format implied by the spec's /stream/{deviceId}/{channel}/{index}.ts
# path (index: integer). Comment/tag lines (starting with '#') are left untouched.
_SEGMENT_LINE_RE = re.compile(r"^(\d+)\.ts\s*$")


def get_playlist(device_id: int, channel: int) -> str:
	"""Fetch the HLS playlist and rewrite segment references to point at
	this app's own proxy endpoint instead of Traccar directly, so the
	browser never needs Traccar credentials to fetch subsequent segments.
	"""
	client = TraccarClient()
	result = client.request(
		"GET",
		"stream_playlist",
		path_params={"deviceId": int(device_id), "channel": int(channel)},
		accept="application/vnd.apple.mpegurl",
	)
	playlist_text = result["data"]
	if not isinstance(playlist_text, str):
		raise TraccarError("Unexpected playlist response from Traccar.", 502)

	rewritten_lines = []
	for line in playlist_text.splitlines():
		match = _SEGMENT_LINE_RE.match(line.strip())
		if match:
			index = match.group(1)
			rewritten_lines.append(
				f"/api/method/erp_tracking.api.get_stream_segment?device_id={int(device_id)}&channel={int(channel)}&index={index}"
			)
		else:
			rewritten_lines.append(line)

	return "\n".join(rewritten_lines)


def get_segment(device_id: int, channel: int, index: int) -> bytes:
	"""Fetch one .ts video segment server-side and return raw bytes."""
	client = TraccarClient()
	result = client.request(
		"GET",
		"stream_segment",
		path_params={"deviceId": int(device_id), "channel": int(channel), "index": int(index)},
		accept="video/mp2t",
	)
	data = result["data"]
	if not isinstance(data, (bytes, bytearray)):
		raise TraccarError("Unexpected segment response from Traccar.", 502)
	return data
