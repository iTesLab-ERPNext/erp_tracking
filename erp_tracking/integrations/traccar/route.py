"""Route module (Section 19).

GET /reports/route returns Position records (not a ReportXxx aggregate
schema), so it's kept separate from reports.py's generic report engine
(Phase 4), which is built around ReportTrips/ReportStops/ReportSummary/
Event schemas. Route is really "position history for possibly multiple
devices/groups" - closer to positions.py than to the aggregate reports.

Per the spec, at least one deviceId or groupId is required.
"""

from __future__ import annotations

from .client import TraccarClient
from .utils import to_iso8601


def get_route(device_ids: list[int] | None = None, group_ids: list[int] | None = None, from_date=None, to_date=None) -> dict:
	if not device_ids and not group_ids:
		return {
			"success": False,
			"data": None,
			"message": "At least one device or group is required.",
			"status_code": 400,
			"error": "TraccarClientValidationError",
		}
	if not from_date or not to_date:
		return {
			"success": False,
			"data": None,
			"message": "Both From and To dates are required.",
			"status_code": 400,
			"error": "TraccarClientValidationError",
		}

	params = {"from": to_iso8601(from_date), "to": to_iso8601(to_date)}
	# requests repeats a list-valued param once per item (deviceId=1&deviceId=2),
	# matching the spec's `style: form` array parameter encoding.
	if device_ids:
		params["deviceId"] = [int(d) for d in device_ids]
	if group_ids:
		params["groupId"] = [int(g) for g in group_ids]

	return TraccarClient().request_safe("GET", "reports_route", params=params)
