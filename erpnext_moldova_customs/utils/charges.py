from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

TAX_DUTY = "020"
TAX_VAT = "030"
POSTING_LCV = "lcv"
POSTING_JE = "journal_entry"
POSTING_ON_PI = "already_on_pi"


def apply_charge_defaults(row) -> None:
	tax = (row.cd_tax_type or "").strip()
	charge_type = (row.charge_type or "").strip()
	if tax == TAX_VAT or charge_type == "vat":
		assert_vat_not_on_lcv(row)
		row.cd_tax_type = tax or TAX_VAT
		row.charge_type = "vat"
		row.default_posting = POSTING_JE
	elif tax == TAX_DUTY or charge_type == "duty":
		row.cd_tax_type = tax or TAX_DUTY
		row.charge_type = "duty"
		if row.default_posting == POSTING_JE:
			row.default_posting = POSTING_LCV
		elif not row.default_posting:
			row.default_posting = POSTING_LCV
	elif not row.default_posting:
		row.default_posting = POSTING_LCV


def assert_vat_not_on_lcv(row) -> None:
	if (row.charge_type or "") == "vat" and (row.default_posting or "") == POSTING_LCV:
		frappe.throw(_("VAT cannot default to Landed Cost Voucher"))


def assert_duty_totals(doc, precision: int = 2) -> None:
	item_duty = sum(flt(row.cd_duty_amount, precision) for row in doc.get("items") or [])
	charge_duty = sum(
		flt(row.cd_amount, precision)
		for row in doc.get("charges") or []
		if (row.cd_tax_type or "").strip() == TAX_DUTY or (row.charge_type or "") == "duty"
	)
	if not (doc.get("charges") or []):
		return
	if charge_duty and abs(item_duty - charge_duty) > (0.5 * 10 ** (-precision)):
		frappe.throw(
			_("Item duty {0} does not match Box 47 duty charges {1}").format(
				flt(item_duty, precision), flt(charge_duty, precision)
			)
		)
