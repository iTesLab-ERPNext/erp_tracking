"""Audit log - GET /audit. Administrator-only on the Traccar side too."""

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.utils import (
	paginate,
	require,
	sort_rows,
	standard_response,
	stringify_attributes,
	to_iso,
)


def fetch_actions(from_time, to_time):
	params = {
		"from": to_iso(require(from_time, "From Date")),
		"to": to_iso(require(to_time, "To Date"), end_of_day=True),
	}
	rows = get_client().get(TRACCAR_ENDPOINTS["audit"], params) or []
	return stringify_attributes(list(rows))


@standard_response
def get_audit_log(from_time, to_time, limit=None, offset=0, sort_by=None, sort_order="desc"):
	rows = sort_rows(fetch_actions(from_time, to_time), sort_by or "actionTime", sort_order)
	return paginate(rows, limit, offset)
