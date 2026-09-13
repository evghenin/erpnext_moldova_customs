# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

from pathlib import Path
from unittest import TestCase, skipUnless

from erpnext_moldova_customs.utils.sad_pdf import SadImportError, parse_pdf, parse_text

APP = Path(__file__).resolve().parents[2]
EXAMPLES = APP / "examples"

LIGO_TEXT = """
UNCTAD/ASYCUDAWorld
CHISINAU1 (PVI, Industriala)
MD207000
LIGO ELECTRIC SA
1024600026571
HOTEL LIFE S.R.L.
IM A
1,882.00EUR 20.2179
4000 000
20,959.43
5,664.71
15,294.72
8.00
20.00
70,808.89
76,473.60
020
030
1 85163100
CH
0.00
0.00
20,959.43
Digitally signed
MoldSign Signature
H1
SAD - Box 31
Itm Description
APARATE ELECTRICE DE USCAT PARUL:
USCATOARE DE PAR MODEL SILENT JET PROTECT 2000 WHITE-6BUC1
V - 55636 - 22/04/2026
Ser - Nbr - Dat
Assessment
R - 45118 - 21/04/2026
Ser - Nbr - Dat
Registration
MD207000 - BRK21869 - 2026 - BRK2186900264
Cuo - Dec - Year - Nbr
Reference
"""


class TestSadPdfParser(TestCase):
	def test_parse_duty_and_vat_from_text(self):
		data = parse_text(LIGO_TEXT)
		self.assertEqual(data["cd_office"], "MD207000")
		self.assertEqual(data["cd_declarant"], "BRK21869")
		self.assertEqual(data["cd_year"], "2026")
		self.assertEqual(data["cd_number"], "BRK2186900264")
		self.assertEqual(data["cd_currency"], "EUR")
		self.assertEqual(data["cd_registration"], "45118")
		self.assertEqual(len(data["items"]), 1)
		item = data["items"][0]
		self.assertEqual(item["cd_hs_code"], "85163100")
		self.assertEqual(item["cd_duty_rate"], 8.0)
		self.assertEqual(item["cd_duty_amount"], 5664.71)
		self.assertEqual(item["cd_stat_value"], 70808.89)
		types = {row["cd_tax_type"] for row in data["charges"]}
		self.assertEqual(types, {"020", "030"})
		self.assertEqual(data["cd_fees_total"], 20959.43)
		self.assertIn("APARATE ELECTRICE DE USCAT PARUL", item["cd_description"])
		self.assertIn("SILENT JET PROTECT", item["cd_description"])

	def test_box31_keeps_marks_and_wrapped_sizes(self):
		from erpnext_moldova_customs.utils.sad_pdf import _apply_box31

		text = """
SAD - Box 31
Itm Description
CICU2841950
LENJERIE DE PAT DIN BUMBAC:
CEARSAF DE PAT CU ELASTIC-168x210+26cm - 100BUC1
CICU2841950
LENJERIE DE TOALETA,DIN BUMBAC:
PROSOP TIP COVORAS DE BAIE P/U PICIOARE-50x80cm-700BUC2
ARTICOLE DE IMBRACAMINTE ALTELE DECAT TRICOTATE SAU CROSETATE:
HALATE DE BAIE DIN BUMBAC- VELUR XL-125x136x54cm-1buc3
ARTICOLE DE IMBRACAMINTE ALTELE DECAT TRICOTATE SAU CROSETATE:
HALAT DE BAIE GOFRAT DIN FIBRE SINTETICE-M 120x110x51cm-100buc; XL 125
x136x54cm-150buc; 3XL 130x162x54cm - 100buc
4
SAD - Containers
"""
		items = [{"cd_item_no": n, "cd_description": ""} for n in range(1, 5)]
		_apply_box31(text, items)
		self.assertTrue(items[0]["cd_description"].startswith("CICU2841950"))
		self.assertIn("100BUC", items[0]["cd_description"])
		self.assertTrue(items[1]["cd_description"].startswith("CICU2841950"))
		self.assertIn("700BUC", items[1]["cd_description"])
		self.assertIn("HALATE DE BAIE DIN BUMBAC", items[2]["cd_description"])
		self.assertIn("XL 125", items[3]["cd_description"])
		self.assertIn("3XL 130x162x54cm", items[3]["cd_description"])


	def test_rejects_non_sad_text(self):
		with self.assertRaises(SadImportError):
			parse_pdf(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")

	@skipUnless(EXAMPLES.is_dir() and any(EXAMPLES.glob("*.pdf")), "local SAD examples not present")
	def test_example_pdfs_reconcile_fees(self):
		for path in sorted(EXAMPLES.glob("*.pdf")):
			with self.subTest(path.name):
				data = parse_pdf(path.read_bytes())
				self.assertGreaterEqual(len(data["items"]), 1)
				self.assertGreaterEqual(len(data["charges"]), 1)
				self.assertNotEqual(data["signature_status"], "Valid")
				duty = sum(row.get("cd_duty_amount") or 0 for row in data["items"])
				charge_duty = sum(
					row["cd_amount"] for row in data["charges"] if row["cd_tax_type"] == "020"
				)
				self.assertAlmostEqual(duty, charge_duty, places=2)
