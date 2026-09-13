# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

import unittest

import frappe
from frappe.utils import flt, nowdate

from erpnext_moldova_customs.erpnext_moldova_customs.doctype.customs_declaration.customs_declaration import (
	verify_pdf_signature,
)
from erpnext_moldova_customs.utils.charges import POSTING_JE, POSTING_LCV
from erpnext_moldova_customs.utils.identity import make_identity_key


def _company():
	name = frappe.get_all("Company", pluck="name", limit=1)
	if not name:
		raise unittest.SkipTest("No Company on test.localhost; DocType tests need ERPNext setup")
	return name[0]


def _cd_kwargs(**extra):
	values = {
		"doctype": "Customs Declaration",
		"company": _company(),
		"cd_office": "MD208000",
		"cd_declarant": "BRK21869",
		"cd_year": "2026",
		"cd_number": "BRK2186900262",
		"cd_date": nowdate(),
		"import_source": "manual",
	}
	values.update(extra)
	return values


class TestCustomsDeclaration(unittest.TestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.db.rollback()

	def test_identity_key_from_asycuda_parts(self):
		doc = frappe.get_doc(_cd_kwargs()).insert()
		self.assertEqual(
			doc.identity_key,
			make_identity_key(doc.company, "MD208000", "BRK21869", "2026", "BRK2186900262"),
		)

	def test_duplicate_identity_key(self):
		frappe.get_doc(_cd_kwargs()).insert()
		dup = frappe.get_doc(_cd_kwargs())
		self.assertRaises(frappe.ValidationError, dup.insert)

	def test_mixed_duty_rates_on_one_declaration(self):
		doc = frappe.get_doc(
			_cd_kwargs(
				cd_number="MIXEDRATES001",
				items=[
					{"cd_item_no": 1, "cd_hs_code": "83014090", "cd_duty_rate": 0, "cd_duty_amount": 0},
					{"cd_item_no": 2, "cd_hs_code": "85163100", "cd_duty_rate": 8, "cd_duty_amount": 100},
					{"cd_item_no": 3, "cd_hs_code": "94032080", "cd_duty_rate": 10, "cd_duty_amount": 200},
					{"cd_item_no": 4, "cd_hs_code": "63023100", "cd_duty_rate": 12, "cd_duty_amount": 300},
					{"cd_item_no": 5, "cd_hs_code": "64041910", "cd_duty_rate": 15, "cd_duty_amount": 400},
				],
			)
		).insert()
		self.assertEqual(flt(doc.cd_duty_total), 1000)
		rates = sorted(row.cd_duty_rate for row in doc.items)
		self.assertEqual(rates, [0, 8, 10, 12, 15])

	def test_vat_cannot_default_to_lcv(self):
		doc = frappe.get_doc(
			_cd_kwargs(
				cd_number="VATONLCV001",
				charges=[
					{
						"cd_tax_type": "030",
						"charge_type": "vat",
						"cd_amount": 50,
						"default_posting": POSTING_LCV,
					}
				],
			)
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_vat_charge_defaults_to_journal_entry(self):
		doc = frappe.get_doc(
			_cd_kwargs(
				cd_number="VATJE001",
				charges=[{"cd_tax_type": "030", "cd_amount": 50}],
			)
		).insert()
		self.assertEqual(doc.charges[0].charge_type, "vat")
		self.assertEqual(doc.charges[0].default_posting, POSTING_JE)
		self.assertEqual(flt(doc.cd_vat_total), 50)

	def test_verify_signatures_requires_original_file(self):
		doc = frappe.get_doc(_cd_kwargs(cd_number="NOSIGFILE001")).insert()
		self.assertRaises(frappe.ValidationError, verify_pdf_signature, doc.name)

	def test_verify_signatures_rejects_scanned_paper(self):
		doc = frappe.get_doc(
			_cd_kwargs(
				cd_number="SCANPAPER001",
				import_source="scanned_paper",
				original_file="/private/files/x.pdf",
			)
		).insert()
		self.assertRaises(frappe.ValidationError, verify_pdf_signature, doc.name)
