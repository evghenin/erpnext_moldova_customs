# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

from unittest import TestCase

from erpnext_moldova_customs.utils.charges import POSTING_JE, POSTING_LCV, apply_charge_defaults
from erpnext_moldova_customs.utils.identity import make_identity_key


class _Row:
	def __init__(self, **kwargs):
		self.cd_tax_type = ""
		self.charge_type = ""
		self.default_posting = None
		for key, value in kwargs.items():
			setattr(self, key, value)


class TestIdentityAndCharges(TestCase):
	def test_identity_key_stable(self):
		a = make_identity_key("Hotel Life", "md208000", "brk21869", 2026, "brk2186900262")
		b = make_identity_key("Hotel Life", "MD208000", "BRK21869", "2026", "BRK2186900262")
		self.assertEqual(a, b)
		self.assertEqual(len(a), 64)

	def test_vat_charge_defaults_to_journal_entry(self):
		row = _Row(cd_tax_type="030")
		apply_charge_defaults(row)
		self.assertEqual(row.charge_type, "vat")
		self.assertEqual(row.default_posting, POSTING_JE)

	def test_duty_charge_defaults_to_lcv(self):
		row = _Row(cd_tax_type="020", default_posting=POSTING_JE)
		apply_charge_defaults(row)
		self.assertEqual(row.charge_type, "duty")
		self.assertEqual(row.default_posting, POSTING_LCV)
