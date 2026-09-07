"""Server statistics - GET /statistics (from and to are both required)."""

from erp_tracking.integrations.traccar.client import get_client
from erp_tracking.integrations.traccar.config import TRACCAR_ENDPOINTS
from erp_tracking.integrations.traccar.utils import require, sort_rows, standard_response, to_iso

METRICS = (
	("activeUsers", "Active Users"),
	("activeDevices", "Active Devices"),
	("requests", "Requests"),
	("messagesReceived", "Messages Received"),
	("messagesStored", "Messages Stored"),
)


def fetch_statistics(from_time, to_time):
	params = {
		"from": to_iso(require(from_time, "From Date")),
		"to": to_iso(require(to_time, "To Date"), end_of_day=True),
	}
	rows = get_client().get(TRACCAR_ENDPOINTS["statistics"], params) or []
	return sort_rows(list(rows), "captureTime", "asc")


@standard_response
def get_statistics(from_time, to_time):
	rows = fetch_statistics(from_time, to_time)
	return {
		"items": rows,
		"labels": [row.get("captureTime") for row in rows],
		"datasets": [
			{"name": label, "values": [row.get(field) or 0 for row in rows]}
			for field, label in METRICS
		],
		"totals": {
			field: sum(row.get(field) or 0 for row in rows) for field, _label in METRICS
		},
	}
