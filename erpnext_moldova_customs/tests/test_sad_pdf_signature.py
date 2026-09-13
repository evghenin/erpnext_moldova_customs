import json
from pathlib import Path
from unittest import TestCase, skipUnless

from erpnext_moldova_customs.utils.sad_pdf_signature import (
	inspect_pdf_signatures,
	verify_pdf_signatures,
)

APP = Path(__file__).resolve().parents[2]
EXAMPLES = APP / "examples"


class TestSadPdfSignature(TestCase):
	@skipUnless(EXAMPLES.is_dir() and any(EXAMPLES.glob("*.pdf")), "local SAD examples not present")
	def test_example_cms_integrity_is_not_full_validity(self):
		path = sorted(EXAMPLES.glob("*.pdf"))[0]
		content = path.read_bytes()
		inspected = inspect_pdf_signatures(content)
		if inspected["signature_status"] == "Not Applicable":
			self.skipTest("Example PDF has no extractable CMS signature fields")
		self.assertEqual(inspected["signature_status"], "Not Checked")
		self.assertEqual(inspected["signature_integrity"], "Not Checked")
		self.assertNotEqual(inspected["signature_status"], "Valid")
		verified = verify_pdf_signatures(content)
		self.assertEqual(verified["signature_integrity"], "Passed")
		self.assertEqual(verified["signature_status"], "Indeterminate")
		self.assertNotEqual(verified["signature_status"], "Valid")
		self.assertEqual(verified["signature_certificate_trust"], "Not Checked")
		self.assertEqual(verified["signature_revocation"], "Not Checked")
		evidence = json.loads(verified["signature_evidence"])
		self.assertGreaterEqual(len(evidence["signatures"]), 1)
		self.assertIn("CMS Verification successful", evidence["signatures"][0]["openssl_message"])

	@skipUnless(EXAMPLES.is_dir() and any(EXAMPLES.glob("*.pdf")), "local SAD examples not present")
	def test_tampered_signed_bytes_are_invalid(self):
		path = sorted(EXAMPLES.glob("*.pdf"))[0]
		original = path.read_bytes()
		if inspect_pdf_signatures(original)["signature_status"] == "Not Applicable":
			self.skipTest("Example PDF has no extractable CMS signature fields")
		content = bytearray(original)
		content[50] ^= 0x01
		verified = verify_pdf_signatures(bytes(content))
		self.assertEqual(verified["signature_integrity"], "Failed")
		self.assertEqual(verified["signature_status"], "Invalid")
