# Copyright (c) 2026, Your Company and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class TraccarCommandLog(Document):
	"""Local audit trail of commands sent through erp_tracking.

	Written only by erp_tracking.api.send_command (see permissions.py -
	sending a command is Manager-only). This is intentionally separate from
	Traccar's own /audit endpoint (Section 33, Phase 7) - that shows
	server-side actions across the whole Traccar server; this shows
	specifically what this ERPNext app sent and who triggered it, insertable
	only from server-side code (in_create permission, no create permission
	granted to any role) so it can't be forged from the client.
	"""

	pass
