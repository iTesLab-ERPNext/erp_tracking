from frappe import _


def get_data():
	return [
		{
			"module_name": "ERP Tracking",
			"category": "Modules",
			"label": _("ERP Tracking"),
			"color": "#2490EF",
			"icon": "octicon octicon-radio-tower",
			"type": "module",
			"description": _("Traccar GPS tracking integration"),
		}
	]
