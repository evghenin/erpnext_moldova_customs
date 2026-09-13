from __future__ import annotations

import io
import re
from decimal import ROUND_HALF_UP, Decimal

MAX_PDF_BYTES = 15 * 1024 * 1024
MONEY = Decimal("0.01")
TAX_DUTY = "020"
TAX_VAT = "030"
KNOWN_TAX = {TAX_DUTY, TAX_VAT}

IDENTITY_RE = re.compile(
	r"(MD\d{6})\s*-\s*([A-Z0-9]+)\s*-\s*(\d{4})\s*-\s*([A-Z0-9]+)\s*\nCuo\s*-\s*Dec\s*-\s*Year\s*-\s*Nbr",
	re.I,
)
REG_RE = re.compile(r"R\s*-\s*(\d+)\s*-\s*(\d{2}/\d{2}/\d{4})")
ASS_RE = re.compile(r"V\s*-\s*(\d+)\s*-\s*(\d{2}/\d{2}/\d{4})")
INVOICE_RE = re.compile(r"([\d,]+\.\d{2})\s*(USD|EUR|MDL|GBP|CNY)\s+([\d.]+)")
HS_RE = re.compile(r"(?m)^(\d{1,2})\s+(\d{8})")
ORPHAN_HS_RE = re.compile(r"(?m)^(\d{8})$")
STACKED_DUTY_VAT_RE = re.compile(
	r"""
	(?P<duty_amt>[\d,]+\.\d{2})\s+
	(?P<vat_amt>[\d,]+\.\d{2})\s+
	(?P<duty_rate>\d+\.\d{2})\s+
	20\.00\s+
	(?P<duty_base>[\d,]+\.\d{2})\s+
	(?P<vat_base>[\d,]+\.\d{2})\s+
	020\s+030
	""",
	re.X,
)
STACKED_VAT_RE = re.compile(
	r"""
	(?P<a>[\d,]+\.\d{2})\s+
	(?P<b>[\d,]+\.\d{2})\s+
	20\.00\s+
	(?P<base>[\d,]+\.\d{2})\s+
	030
	""",
	re.X,
)
GLUED_RE = re.compile(
	r"(?<!\d)(\d)(\d{1,3}(?:,\d{3})*\.\d{2})(\d+\.\d{2})(\d{1,3}(?:,\d{3})*\.\d{2})(0[23]0)"
)
STAT_RE = re.compile(r"([\d,]+\.\d{2})\s*\n20[0-9]\b")
BOX42_RE = re.compile(r"([\d,]+\.\d{2})\s+1\s*\n42 Item Price")
NET_MASS_RE = re.compile(r"(\d+\.\d{4})")
ORIGIN_RE = re.compile(r"\b([A-Z]{2})\b")
IDNO_RE = re.compile(r"\b(\d{13})\b")
FEES_RE = re.compile(r"0\.00\s+0\.00\s+([\d,]+\.\d{2})")
TOTAL_PAGE_RE = re.compile(r"Total Page\s+([\d,]+\.\d{2})")
DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class SadImportError(Exception):
	pass


def money(value) -> Decimal:
	if isinstance(value, Decimal):
		qty = value
	else:
		qty = Decimal(str(value).replace(",", "").replace(" ", "") or "0")
	return qty.quantize(MONEY, rounding=ROUND_HALF_UP)


def _iso_date(value: str) -> str:
	m = DATE_RE.search(value or "")
	if not m:
		raise SadImportError("Registration or assessment date is missing")
	return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"


def extract_text(content: bytes) -> tuple[str, object]:
	from pypdf import PdfReader

	if len(content) > MAX_PDF_BYTES or not content.startswith(b"%PDF-"):
		raise SadImportError("Upload a SAD PDF smaller than 15 MB")
	try:
		reader = PdfReader(io.BytesIO(content))
		if reader.is_encrypted:
			raise SadImportError("Unable to read this PDF")
		pages = [(page.extract_text() or "") for page in reader.pages]
	except SadImportError:
		raise
	except Exception as exc:
		raise SadImportError("Unable to read this PDF") from exc
	text = "\n".join(pages)
	if "UNCTAD" not in text and "Cuo - Dec - Year - Nbr" not in text:
		raise SadImportError("This is not an ASYCUDA / SAD PDF")
	return text, reader


def _parse_identity(text: str) -> dict:
	m = IDENTITY_RE.search(text)
	if not m:
		raise SadImportError("Declaration reference (office / declarant / year / number) is missing")
	reg = REG_RE.search(text)
	ass = ASS_RE.search(text)
	inv = INVOICE_RE.search(text)
	if not inv:
		raise SadImportError("Box 22 invoice amount is missing")
	idnos = IDNO_RE.findall(text)
	importer = re.search(r"(\d{13})\s*\n([^\n]+)", text)
	office_name = re.search(r"(MD\d{6})\n([^\n]+)", text)
	return {
		"cd_office": m.group(1).upper(),
		"cd_declarant": m.group(2).upper(),
		"cd_year": m.group(3),
		"cd_number": m.group(4).upper(),
		"cd_registration": reg.group(1) if reg else "",
		"cd_registration_date": _iso_date(reg.group(2)) if reg else None,
		"cd_assessment": ass.group(1) if ass else "",
		"cd_assessment_date": _iso_date(ass.group(2)) if ass else None,
		"cd_date": _iso_date(reg.group(2)) if reg else None,
		"cd_currency": inv.group(2),
		"cd_conversion_rate": float(inv.group(3)),
		"cd_invoice_amount": float(money(inv.group(1))),
		"cd_importer_idno": importer.group(1) if importer else (idnos[0] if idnos else ""),
		"cd_importer_name": (importer.group(2).strip() if importer else ""),
		"cd_exporter_name": (office_name.group(2).strip() if office_name else ""),
		"cd_procedure": "4000 000" if "4000 000" in text else "",
		"declaration_type": "H1" if re.search(r"\bH1\b", text) else "",
		"regime": "IM A" if "IM A" in text else "",
	}


def _printed_fees(text: str) -> Decimal:
	pages = TOTAL_PAGE_RE.findall(text)
	if pages:
		return money(pages[-1])
	m = FEES_RE.search(text)
	if m:
		return money(m.group(1))
	raise SadImportError("Printed total fees are missing")


def _tax_tuple(item_no, tax_type, rate, base, amount) -> dict:
	return {
		"cd_item_no": int(item_no) if item_no else 0,
		"cd_tax_type": tax_type,
		"cd_rate": float(money(rate)),
		"cd_tax_base": float(money(base)),
		"cd_amount": float(money(amount)),
	}


def _parse_taxes(text: str) -> list[dict]:
	rows: list[dict] = []
	seen: set[tuple] = set()

	def add(row: dict):
		key = (row["cd_tax_type"], row["cd_amount"], row["cd_tax_base"], row["cd_rate"])
		if key in seen:
			return
		if row["cd_tax_type"] not in KNOWN_TAX:
			return
		if row["cd_amount"] <= 0:
			return
		seen.add(key)
		rows.append(row)

	amount_type_ranges = []
	for marker in re.finditer(r"AmountType", text):
		end = text.find("Total Page", marker.start())
		amount_type_ranges.append((marker.start(), end if end != -1 else marker.start() + 250))

	def in_amount_type(pos: int) -> bool:
		return any(start <= pos < end for start, end in amount_type_ranges)

	for m in STACKED_DUTY_VAT_RE.finditer(text):
		if in_amount_type(m.start()):
			continue
		add(_tax_tuple(0, TAX_DUTY, m["duty_rate"], m["duty_base"], m["duty_amt"]))
		add(_tax_tuple(0, TAX_VAT, "20.00", m["vat_base"], m["vat_amt"]))

	for m in STACKED_VAT_RE.finditer(text):
		if in_amount_type(m.start()):
			continue
		if STACKED_DUTY_VAT_RE.search(text[max(0, m.start() - 80) : m.end() + 10]):
			continue
		amt = money(m["b"])
		if money(m["a"]) == amt:
			amt = money(m["a"])
		add(_tax_tuple(0, TAX_VAT, "20.00", m["base"], amt))

	for m in GLUED_RE.finditer(text):
		add(_tax_tuple(m.group(1), m.group(5), m.group(3), m.group(4), m.group(2)))

	if not rows:
		raise SadImportError("Box 47 tax lines are missing")
	return rows


def _parse_items(text: str) -> list[dict]:
	found = [(int(n), hs, m.start()) for m in HS_RE.finditer(text) for n, hs in [m.groups()]]
	used = {hs for _, hs, _ in found}
	orphans = []
	for m in ORPHAN_HS_RE.finditer(text):
		hs = m.group(1)
		if hs in used or hs.startswith("10246"):
			continue
		orphans.append((hs, m.start()))
		used.add(hs)

	numbers = sorted({n for n, _, _ in found})
	missing = []
	if numbers:
		for i in range(1, max(numbers) + 1 + len(orphans)):
			if i not in numbers:
				missing.append(i)
	items = []
	for n, hs, pos in found:
		items.append(_item_from_window(text, n, hs, pos))
	for hs, pos in orphans:
		item_no = missing.pop(0) if missing else (max((i["cd_item_no"] for i in items), default=0) + 1)
		items.append(_item_from_window(text, item_no, hs, pos))
	items.sort(key=lambda row: row["cd_item_no"])
	uniq = {}
	for row in items:
		uniq.setdefault(row["cd_item_no"], row)
	items = list(uniq.values())
	if not items:
		raise SadImportError("Commodity codes are missing")
	_apply_box31(text, items)
	return items


def _item_from_window(text: str, item_no: int, hs: str, pos: int) -> dict:
	start = max(0, pos - 500) if item_no == 1 else pos
	window = text[start : pos + 900]
	origin = ""
	om = ORIGIN_RE.search(window[8:120])
	if om and om.group(1) not in {"MD", "IM", "PX", "ZZ", "BX", "NO"}:
		origin = om.group(1)
	if re.search(r"\b(CN|TR|PL|IT|CH|DE|RO|UA|BG|AT|FR|ES|NL|BE|GB|US)\b", window[:200]):
		origin = re.search(
			r"\b(CN|TR|PL|IT|CH|DE|RO|UA|BG|AT|FR|ES|NL|BE|GB|US)\b", window[:200]
		).group(1)
	masses = NET_MASS_RE.findall(window)
	box42 = BOX42_RE.search(window)
	stats = [money(v) for v in re.findall(r"([\d,]+\.\d{2})", window[:500])]
	stat_ai = STAT_RE.search(text[max(0, pos - 50) : pos + 700])
	return {
		"cd_item_no": item_no,
		"cd_hs_code": hs,
		"cd_origin": origin,
		"cd_description": "",
		"cd_qty": 0,
		"cd_net_mass": float(masses[0]) if masses else 0,
		"cd_gross_mass": float(masses[1]) if len(masses) > 1 else 0,
		"cd_value": float(money(box42.group(1))) if box42 else 0,
		"cd_stat_value": float(money(stat_ai.group(1))) if stat_ai else 0,
		"_stat_candidates": [float(v) for v in stats],
	}


def _apply_box31(text: str, items: list[dict]) -> None:
	m = re.search(r"SAD - Box 31\s+Itm Description\s+(.*?)(?:SAD - Containers|\Z)", text, re.S)
	if not m:
		return
	body = m.group(1).strip()
	body = re.split(r"\n(?:V|R)\s+-\s+\d+", body, maxsplit=1)[0].strip()
	item_nos = sorted({row["cd_item_no"] for row in items})
	if not item_nos:
		return
	descs: dict[int, str] = {}
	cursor = 0
	for item_no in item_nos:
		pattern = rf"(?m)(?:(?<=[A-Za-z]){item_no}$|^{item_no}$)"
		hit = re.search(pattern, body[cursor:])
		if not hit:
			continue
		descs[item_no] = body[cursor : cursor + hit.start()].strip()
		cursor = cursor + hit.end()
	for row in items:
		row["cd_description"] = descs.get(row["cd_item_no"], "")[:1000]


def _assign_taxes(items: list[dict], taxes: list[dict]) -> None:
	by_base: dict[float, list[dict]] = {}
	for row in items:
		for cand in [row["cd_stat_value"], *row.get("_stat_candidates", [])]:
			by_base.setdefault(float(money(cand)), []).append(row)

	def find_item(base: float, extra: float = 0) -> dict | None:
		target = float(money(Decimal(str(base)) - Decimal(str(extra))))
		hits = by_base.get(target) or by_base.get(float(money(base)))
		if hits:
			return hits[0]
		for row in items:
			for cand in [row["cd_stat_value"], *row.get("_stat_candidates", [])]:
				if abs(float(money(cand)) - target) <= 0.05:
					return row
		return None

	duty_by_item: dict[int, dict] = {}
	unused = []
	for tax in taxes:
		if tax["cd_tax_type"] == TAX_DUTY:
			item = find_item(tax["cd_tax_base"])
			if item:
				tax["cd_item_no"] = item["cd_item_no"]
				item["cd_stat_value"] = tax["cd_tax_base"]
				item["cd_duty_rate"] = tax["cd_rate"]
				item["cd_duty_amount"] = tax["cd_amount"]
				duty_by_item[item["cd_item_no"]] = tax
			else:
				unused.append(tax)
		else:
			unused.append(tax)

	still = []
	for tax in unused:
		if tax["cd_tax_type"] != TAX_VAT:
			still.append(tax)
			continue
		item = None
		for row in items:
			duty = duty_by_item.get(row["cd_item_no"])
			if duty and abs(
				float(money(Decimal(str(duty["cd_tax_base"])) + Decimal(str(duty["cd_amount"]))))
				- tax["cd_tax_base"]
			) <= 0.05:
				item = row
				break
		if not item:
			item = find_item(tax["cd_tax_base"])
		if item:
			tax["cd_item_no"] = item["cd_item_no"]
			if not item["cd_stat_value"]:
				item["cd_stat_value"] = tax["cd_tax_base"]
		still.append(tax)

	for row in items:
		row.pop("_stat_candidates", None)
		row.setdefault("cd_duty_rate", 0)
		row.setdefault("cd_duty_amount", 0)

	if len(items) == 1:
		only = items[0]
		for tax in taxes:
			if not tax.get("cd_item_no"):
				tax["cd_item_no"] = only["cd_item_no"]
			if tax["cd_tax_type"] == TAX_DUTY:
				only["cd_stat_value"] = tax["cd_tax_base"]
				only["cd_duty_rate"] = tax["cd_rate"]
				only["cd_duty_amount"] = tax["cd_amount"]


def parse_text(text: str) -> dict:
	header = _parse_identity(text)
	items = _parse_items(text)
	taxes = _parse_taxes(text)
	_assign_taxes(items, taxes)
	fees = _printed_fees(text)
	charge_total = money(sum(Decimal(str(t["cd_amount"])) for t in taxes))
	if abs(charge_total - fees) > Decimal("0.05"):
		raise SadImportError(
			f"Box 47 amounts {charge_total} do not match printed total fees {fees}"
		)
	return {
		**header,
		"items": items,
		"charges": taxes,
		"cd_fees_total": float(fees),
	}


def parse_pdf(content: bytes) -> dict:
	text, _reader = extract_text(content)
	parsed = parse_text(text)
	from erpnext_moldova_customs.utils.sad_pdf_signature import inspect_pdf_signatures

	parsed.update(inspect_pdf_signatures(content))
	if parsed.get("signature_status") == "Valid":
		parsed["signature_status"] = "Indeterminate"
	parsed["import_source"] = "signed_pdf"
	return parsed
