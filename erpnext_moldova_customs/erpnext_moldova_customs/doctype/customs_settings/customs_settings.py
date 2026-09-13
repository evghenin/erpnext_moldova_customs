# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CustomsSettings(Document):
	def validate(self):
		seen = set()
		for row in self.get("company_settings") or []:
			if not row.company:
				continue
			if row.company in seen:
				frappe.throw(_("Company {0} is listed more than once").format(row.company))
			seen.add(row.company)
