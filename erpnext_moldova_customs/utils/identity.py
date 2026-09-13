from __future__ import annotations

import hashlib

import frappe


def make_identity_key(company: str, office: str, declarant: str, year, decl_nbr: str) -> str:
	parts = [
		(company or "").strip(),
		(office or "").strip().upper(),
		(declarant or "").strip().upper(),
		str(year or "").strip(),
		(decl_nbr or "").strip().upper(),
	]
	return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def lock_company(company: str) -> None:
	frappe.db.sql("select name from `tabCompany` where name=%s for update", company)
