"""Top-level whitelisted API surface for erp_tracking.

Phase 1 only exposes connection status, used by the Dashboard's 🟢/🔴
Connected indicator (Section 36). Feature-specific whitelisted methods
(get_devices, get_positions, generate_report, send_command, ...) are added
here in their respective phases, but each delegates to its own
integrations/traccar/<feature>.py module rather than talking to
TraccarClient directly - this file stays a thin router, never business logic.
"""

from __future__ import annotations

import frappe

from erp_tracking.integrations.traccar.config import get_settings
from erp_tracking.integrations.traccar.exceptions import TraccarConfigurationError


@frappe.whitelist()
def get_connection_status():
	"""Lightweight, read-only status check for dashboard widgets.

	Does NOT make a network call - it reports the last cached result from
	Traccar Settings (populated by the Test Connection button). This keeps
	dashboard loads fast; use test_connection() for an active check.
	"""
	settings_doc = frappe.get_single("Traccar Settings")

	try:
		get_settings()
		configured = True
	except TraccarConfigurationError:
		configured = False

	return {
		"configured": configured,
		"enabled": bool(settings_doc.enabled),
		"connection_status": settings_doc.connection_status or "Not Tested",
		"last_connection_test": settings_doc.last_connection_test,
	}
