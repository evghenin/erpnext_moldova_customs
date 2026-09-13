# Copyright (c) 2026, Evgheni Nemerenco and contributors
# For license information, please see license.txt

from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from erpnext_moldova_customs.utils.charges import (
	TAX_DUTY,
	TAX_VAT,
	apply_charge_defaults,
	assert_duty_totals,
	assert_vat_not_on_lcv,
)
from erpnext_moldova_customs.utils.identity import lock_company, make_identity_key
from erpnext_moldova_customs.utils.sad_pdf_signature import verify_pdf_signatures
from erpnext_moldova_customs.utils.timeline import log_event

SIGNATURE_FIELDS = (
	"signature_status",
	"signature_integrity",
	"signature_format",
	"signature_field",
	"signature_declared_time",
	"signature_coverage",
	"signature_certificate_trust",
	"signature_revocation",
	"signature_timestamp_check",
	"signature_evidence",
	"signature_checked_on",
	"signature_checked_by",
)


class CustomsDeclaration(Document):
	def validate(self):
		if not self.company:
			frappe.throw(_("Select a Company"))
		lock_company(self.company)
		self.cd_office = (self.cd_office or "").strip().upper()
		self.cd_declarant = (self.cd_declarant or "").strip().upper()
		self.cd_number = (self.cd_number or "").strip().upper()
		self.cd_year = str(self.cd_year or "").strip()
		self._apply_charges()
		self._calculate_totals()
		assert_duty_totals(self)
		self._set_identity()
		self._hash_original()

	def _apply_charges(self):
		for row in self.get("charges") or []:
			apply_charge_defaults(row)
			assert_vat_not_on_lcv(row)

	def _calculate_totals(self):
		self.cd_stat_value_total = sum(flt(row.cd_stat_value) for row in self.get("items") or [])
		self.cd_duty_total = sum(flt(row.cd_duty_amount) for row in self.get("items") or [])
		vat = sum(
			flt(row.cd_amount)
			for row in self.get("charges") or []
			if (row.cd_tax_type or "").strip() == TAX_VAT or (row.charge_type or "") == "vat"
		)
		self.cd_vat_total = vat
		self.cd_fees_total = flt(self.cd_duty_total) + flt(self.cd_vat_total)

	def _set_identity(self):
		self.identity_key = make_identity_key(
			self.company, self.cd_office, self.cd_declarant, self.cd_year, self.cd_number
		)
		duplicates = frappe.get_all(
			"Customs Declaration",
			filters={"identity_key": self.identity_key, "name": ["!=", self.name], "docstatus": ["<", 2]},
			pluck="name",
		)
		if duplicates:
			frappe.throw(_("This declaration is already registered as {0}").format(duplicates[0]))

	def _hash_original(self):
		if not self.original_file:
			self.file_hash = self.file_hash or ""
			return
		file_name = frappe.db.get_value("File", {"file_url": self.original_file}, "name")
		if not file_name:
			return
		content = frappe.get_doc("File", file_name).get_content()
		if content is None:
			return
		if isinstance(content, str):
			content = content.encode()
		self.file_hash = hashlib.sha256(content).hexdigest()


def _file_bytes(file_doc):
	path = file_doc.get_full_path()
	try:
		with open(path, "rb") as handle:
			return handle.read()
	except OSError:
		content = file_doc.get_content()
		return content.encode("utf-8") if isinstance(content, str) else content


@frappe.whitelist()
def import_pdf(file_url: str, company: str):
	frappe.has_permission("Customs Declaration", "create", throw=True)
	frappe.get_doc("Company", company).check_permission("read")
	from erpnext_moldova_customs.utils.identity import make_identity_key
	from erpnext_moldova_customs.utils.sad_pdf import SadImportError, parse_pdf

	file_doc = _read_original(file_url)
	content = _file_bytes(file_doc)
	try:
		parsed = parse_pdf(content)
	except SadImportError as exc:
		frappe.throw(_(str(exc)), title=_("Cannot read SAD"))

	key = make_identity_key(
		company, parsed["cd_office"], parsed["cd_declarant"], parsed["cd_year"], parsed["cd_number"]
	)
	existing = frappe.db.get_value(
		"Customs Declaration", {"identity_key": key, "docstatus": ["<", 2]}, "name"
	)
	if existing:
		frappe.get_doc("Customs Declaration", existing).check_permission("read")
		frappe.msgprint(
			_("This declaration is already registered as {0}").format(existing),
			indicator="yellow",
			alert=True,
		)
		return existing

	doc = frappe.get_doc(
		{
			"doctype": "Customs Declaration",
			"company": company,
			"import_source": "signed_pdf",
			"declaration_type": parsed.get("declaration_type") or "H1",
			"regime": parsed.get("regime") or "IM A",
			"cd_office": parsed["cd_office"],
			"cd_declarant": parsed["cd_declarant"],
			"cd_year": parsed["cd_year"],
			"cd_number": parsed["cd_number"],
			"cd_date": parsed.get("cd_date"),
			"cd_registration": parsed.get("cd_registration"),
			"cd_registration_date": parsed.get("cd_registration_date"),
			"cd_assessment": parsed.get("cd_assessment"),
			"cd_assessment_date": parsed.get("cd_assessment_date"),
			"cd_importer_idno": parsed.get("cd_importer_idno"),
			"cd_importer_name": parsed.get("cd_importer_name"),
			"cd_exporter_name": parsed.get("cd_exporter_name"),
			"cd_procedure": parsed.get("cd_procedure"),
			"cd_currency": parsed.get("cd_currency"),
			"cd_conversion_rate": parsed.get("cd_conversion_rate"),
			"cd_invoice_amount": parsed.get("cd_invoice_amount"),
			"original_file": file_url,
			"items": parsed["items"],
			"charges": parsed["charges"],
		}
	)
	try:
		verified = _verified_signature_values(content)
	except SadImportError as exc:
		frappe.throw(_(str(exc)))
	for field in SIGNATURE_FIELDS:
		if field in verified:
			doc.set(field, verified.get(field))
	if doc.signature_status == "Valid":
		doc.signature_status = "Indeterminate"
	doc.insert()
	log_event(
		doc,
		"checked the PDF signature: integrity {0}, overall {1}",
		doc.signature_integrity,
		doc.signature_status,
	)
	frappe.db.set_value(
		"File",
		file_doc.name,
		{"attached_to_doctype": "Customs Declaration", "attached_to_name": doc.name, "is_private": 1},
		update_modified=False,
	)
	frappe.msgprint(
		_("Customs Declaration {0} imported").format(doc.name),
		indicator="green",
		alert=True,
	)
	return doc.name


def _get_cd(name):
	doc = frappe.get_doc("Customs Declaration", name)
	doc.check_permission("write")
	return doc


def _verified_signature_values(content: bytes) -> dict:
	result = verify_pdf_signatures(content)
	from frappe.utils import now_datetime

	if result.get("signature_status") == "Valid":
		result["signature_status"] = "Indeterminate"
	result["signature_checked_on"] = now_datetime()
	result["signature_checked_by"] = frappe.session.user
	return result


@frappe.whitelist()
def verify_pdf_signature(name: str):
	doc = _get_cd(name)
	if (doc.import_source or "") == "scanned_paper":
		frappe.throw(_("Paper originals have no PDF signature to verify"))
	if not doc.original_file:
		frappe.throw(_("Attach the electronic original"))
	content = _file_bytes(_read_original(doc.original_file))
	if not content.startswith(b"%PDF-"):
		frappe.throw(_("PDF signature verification requires the original PDF"))
	from erpnext_moldova_customs.utils.sad_pdf import SadImportError

	try:
		result = _verified_signature_values(content)
	except SadImportError as exc:
		frappe.throw(_(str(exc)))
	for field in SIGNATURE_FIELDS:
		doc.db_set(field, result.get(field), update_modified=True)
	log_event(
		doc,
		"checked the PDF signature: integrity {0}, overall {1}",
		result["signature_integrity"],
		result["signature_status"],
	)
	return {field: result.get(field) for field in SIGNATURE_FIELDS}


def _read_original(file_url):
	files = frappe.get_all("File", filters={"file_url": file_url}, pluck="name", limit=2)
	if not files:
		frappe.throw(_("Original file not found or access denied"), frappe.PermissionError)
	file_doc = frappe.get_doc("File", files[0])
	file_doc.check_permission("read")
	if not file_doc.is_private:
		frappe.throw(_("Upload the original as a private file"))
	return file_doc


@frappe.whitelist()
def save_uploaded_original():
	frappe.has_permission("Customs Declaration", "create", throw=True)
	content = getattr(frappe.local, "uploaded_file", None)
	filename = getattr(frappe.local, "uploaded_filename", None) or "original.pdf"
	if not content:
		frappe.throw(_("No file uploaded"))
	if isinstance(content, str):
		content = content.encode("utf-8")
	file_doc = frappe.new_doc("File")
	file_doc.file_name = filename
	private = frappe.form_dict.get("is_private")
	file_doc.is_private = 1 if private in (None, "") else cint(private)
	file_doc.folder = frappe.form_dict.folder or "Home"
	file_doc.content = content
	file_doc.insert(ignore_permissions=True)
	return file_doc
