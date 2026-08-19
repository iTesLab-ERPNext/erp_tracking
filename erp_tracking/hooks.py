from . import __version__ as app_version

app_name = "erp_tracking"
app_title = "ERP Tracking"
app_publisher = "Your Company"
app_description = "Traccar GPS tracking integration for ERPNext v15"
app_email = "support@example.com"
app_license = "MIT"

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
# Roles created by this app are exported/imported as fixtures so they survive
# `bench migrate` and can be version controlled. The actual Role records are
# created idempotently in erp_tracking.install.after_install as well, so a
# fresh install always has them even before fixtures are synced.
fixtures = [
	{
		"doctype": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"ERP Tracking Manager",
					"ERP Tracking User",
					"ERP Tracking Viewer",
				],
			]
		],
	},
]

# -----------------------------------------------------------------------------
# Installation hooks
# -----------------------------------------------------------------------------
after_install = "erp_tracking.install.after_install"

# -----------------------------------------------------------------------------
# Website / Desk assets
# -----------------------------------------------------------------------------
# Loaded on every Desk page so any ERP Tracking page (or a future custom
# report) can use erp_tracking.ListEngine / erp_tracking.status_badge
# without each page re-declaring the dependency.
app_include_js = ["/assets/erp_tracking/js/erp_tracking_list_engine.js"]
app_include_css = []

doctype_js = {
	# "Traccar Settings" JS is auto-loaded by Frappe from the doctype folder,
	# this map is reserved for future per-doctype client script overrides.
}

# -----------------------------------------------------------------------------
# Scheduled tasks (reserved for later phases: cache refresh, health polling)
# -----------------------------------------------------------------------------
scheduler_events = {
	# "cron": {
	# 	"*/5 * * * *": [
	# 		"erp_tracking.integrations.traccar.server.refresh_health_cache"
	# 	]
	# }
}
