"""Reusable server-side export system (CSV / XLSX / PDF).

Rules enforced here:

* Exports always run on the server - never assembled in browser JavaScript.
* Traccar's own ``xlsx`` endpoints are preferred where the specification
  defines them; CSV and PDF are rendered by Frappe because Traccar has no such
  endpoints.
* The export always uses the same filters as the page that requested it.
"""

import csv
import io

import frappe
from frappe import _
from frappe.utils import cstr, format_datetime, now_datetime
from frappe.utils.pdf import get_pdf
from frappe.utils.xlsxutils import make_xlsx

from erp_tracking.integrations.traccar.config import EXPORT_FORMATS
from erp_tracking.integrations.traccar.exceptions import TraccarAPIError

MIME_TYPES = {
	"csv": "text/csv",
	"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	"pdf": "application/pdf",
}

MAX_EXPORT_ROWS = 50000


def validate_format(fmt):
	fmt = cstr(fmt).lower()
	if fmt not in EXPORT_FORMATS:
		raise TraccarAPIError(_("Unsupported export format."), 400)
	return fmt


def _cell(row, column):
	value = row.get(column["fieldname"])
	if value is None:
		return ""
	if column.get("fieldtype") == "Datetime" and value:
		try:
			return format_datetime(cstr(value).replace("Z", ""))
		except Exception:  # noqa: BLE001
			return cstr(value)
	if column.get("fieldtype") == "Check":
		return _("Yes") if value else _("No")
	return cstr(value)


def to_csv(rows, columns):
	buffer = io.StringIO()
	writer = csv.writer(buffer)
	writer.writerow([_(c["label"]) for c in columns])
	for row in rows:
		writer.writerow([_cell(row, c) for c in columns])
	return buffer.getvalue().encode("utf-8-sig")


def to_xlsx(rows, columns, sheet_name="Export"):
	data = [[_(c["label"]) for c in columns]]
	for row in rows:
		data.append([_cell(row, c) for c in columns])
	return make_xlsx(data, cstr(sheet_name)[:30] or "Export").getvalue()


def to_pdf(rows, columns, title, meta_lines=None):
	html = frappe.render_template(
		"erp_tracking/templates/includes/export.html",
		{
			"title": title,
			"columns": [_(c["label"]) for c in columns],
			"rows": [[_cell(row, c) for c in columns] for row in rows],
			"meta_lines": meta_lines or [],
			"generated_on": format_datetime(now_datetime()),
			"row_count": len(rows),
		},
	)
	return get_pdf(html, options={"orientation": "Landscape"})


def build(rows, columns, fmt, title="Export", meta_lines=None):
	"""Render ``rows`` in ``fmt`` and return ``(bytes, mime, extension)``."""
	fmt = validate_format(fmt)
	rows = list(rows or [])[:MAX_EXPORT_ROWS]

	if fmt == "csv":
		return to_csv(rows, columns), MIME_TYPES["csv"], "csv"
	if fmt == "xlsx":
		return to_xlsx(rows, columns, title), MIME_TYPES["xlsx"], "xlsx"
	return to_pdf(rows, columns, title, meta_lines), MIME_TYPES["pdf"], "pdf"


def send_download(content, filename, mime=None):
	"""Attach the payload to the current Frappe response as a download."""
	frappe.local.response.filename = filename
	frappe.local.response.filecontent = content
	frappe.local.response.type = "binary"
	if mime:
		frappe.local.response.display_content_as = "attachment"
	return


def build_filename(prefix, fmt, filters=None):
	stamp = now_datetime().strftime("%Y%m%d-%H%M%S")
	parts = [cstr(prefix).replace(" ", "-").lower(), stamp]
	return f"{'-'.join(parts)}.{fmt}"
