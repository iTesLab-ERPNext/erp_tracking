app_name = "erp_tracking"
app_title = "ERP Tracking"
app_publisher = "ERP Tracking"
app_description = "Traccar GPS tracking integration for ERPNext v15"
app_email = "support@example.com"
app_license = "MIT"

required_apps = ["frappe/erpnext"]

# ---------------------------------------------------------------------------
# Assets (built by `bench build`)
# ---------------------------------------------------------------------------
app_include_js = ["erp_tracking.bundle.js"]
app_include_css = ["erp_tracking.bundle.css"]

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------
after_install = "erp_tracking.install.after_install"
after_migrate = "erp_tracking.install.after_migrate"

# ---------------------------------------------------------------------------
# Fixtures / translations
# ---------------------------------------------------------------------------
# Translations live in erp_tracking/translations/*.csv and are picked up by
# `bench --site <site> migrate` automatically.

# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------
scheduler_events = {
	"hourly": [
		"erp_tracking.api.refresh_connection_status",
	],
}

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
# before_tests = "erp_tracking.install.before_tests"
