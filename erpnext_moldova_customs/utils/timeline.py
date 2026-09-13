"""Timeline Info logs for Customs Declaration actions.

Activity text is stored as an English msgid + args JSON payload so the desk
timeline can translate it in the viewer's language.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cstr

CD_LOG_PREFIX = "cd:"


def log_event(doc, msgid: str, *args, translate_args: list[int] | tuple[int, ...] | None = None) -> None:
	if not doc or not getattr(doc, "name", None) or doc.is_new():
		return
	if frappe.flags.in_install or frappe.flags.in_migrate or frappe.flags.in_patch or frappe.flags.in_import:
		return
	try:
		msgid = cstr(msgid or "").strip()
		if not msgid:
			return
		if msgid.startswith(CD_LOG_PREFIX):
			msgid = msgid[len(CD_LOG_PREFIX) :]
		payload = {
			"msgid": msgid,
			"args": [cstr(a) for a in args],
		}
		if translate_args:
			payload["translate_args"] = [int(i) for i in translate_args]
		doc.add_comment("Info", CD_LOG_PREFIX + frappe.as_json(payload, indent=None, separators=(",", ":")))
	except Exception:
		frappe.log_error(title="Customs timeline log failed", message=frappe.get_traceback())


def _extractable_log_messages():
	return (_("checked the PDF signature: integrity {0}, overall {1}"),)
