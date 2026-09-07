"""Traccar Settings - the single, server-side home of the integration config."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, cstr


class TraccarSettings(Document):
	def validate(self):
		self.normalise_url()
		self.validate_timeout()
		self.validate_credentials()
		self.reset_status_on_change()

	def on_update(self):
		# Any configuration change invalidates cached payloads and the cached
		# credential check.
		from erp_tracking.integrations.traccar.auth import TraccarAuth
		from erp_tracking.integrations.traccar.utils import clear_cache

		TraccarAuth(self).clear_session()
		clear_cache()

	# -- validation ------------------------------------------------------
	def normalise_url(self):
		url = cstr(self.traccar_url).strip().rstrip("/")
		if url and not url.startswith(("http://", "https://")):
			frappe.throw(_("Traccar API URL must start with http:// or https://"))
		self.traccar_url = url

	def validate_timeout(self):
		timeout = cint(self.timeout)
		if not timeout:
			self.timeout = 30
		elif timeout < 1 or timeout > 300:
			frappe.throw(_("Timeout must be between 1 and 300 seconds."))

		if cint(self.default_page_length) <= 0:
			self.default_page_length = 20
		if cint(self.cache_ttl) < 0:
			self.cache_ttl = 0

	def validate_credentials(self):
		if not cint(self.enabled):
			return

		if not self.traccar_url:
			frappe.throw(_("Set the Traccar API URL before enabling the integration."))

		if self.auth_type == "API Key":
			if not self.get_password("api_key", raise_exception=False):
				frappe.throw(_("Set the API key before enabling the integration."))
		else:
			if not self.username or not self.get_password("password", raise_exception=False):
				frappe.throw(_("Set the username and password before enabling the integration."))

	def reset_status_on_change(self):
		"""A credential or URL edit invalidates the previous test result."""
		if self.is_new():
			return

		watched = ("traccar_url", "auth_type", "username", "password", "api_key", "verify_ssl")
		if any(self.has_value_changed(field) for field in watched):
			self.connection_status = "Not Tested"
			self.last_error = None
