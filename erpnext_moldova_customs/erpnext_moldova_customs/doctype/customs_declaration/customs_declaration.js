frappe.ui.form.on("Customs Declaration", {
	refresh(frm) {
		if (frappe.model.can_create("Customs Declaration")) {
			const bind = () => {
				const cd = frappe.provide("erpnext_moldova_customs.cd");
				if (!cd.bind_import_buttons) {
					return false;
				}
				cd.bind_import_buttons((label, action) => {
					frm.add_custom_button(label, action);
				});
				return true;
			};
			if (!bind()) {
				frappe.require("/assets/erpnext_moldova_customs/js/customs_declaration_import.js", bind);
			}
		}
		if (frm.doc.docstatus === 0 && frm.doc.original_file) {
			frm.set_intro(
				__("Imported original values are preserved. Map ERP items and check amounts before posting."),
				"blue"
			);
		} else {
			frm.set_intro();
		}
	},
});

function cd_signature_filename(frm) {
	const url = String((frm.doc && frm.doc.original_file) || "");
	try {
		return decodeURIComponent(url.split("/").pop() || frm.doc.name);
	} catch (e) {
		return frm.doc.name;
	}
}

function cd_parse_signature_evidence(raw) {
	if (!raw) return { signatures: [], overall: "" };
	if (typeof raw === "object") return raw;
	try {
		return JSON.parse(raw);
	} catch (e) {
		return { signatures: [], overall: "" };
	}
}

function cd_sig_badge(ok) {
	const color = ok ? "green" : "red";
	const label = ok ? __("Valid") : __("Invalid");
	return `<span class="indicator-pill ${color} no-indicator-dot">${frappe.utils.escape_html(
		label
	)}</span>`;
}

function cd_verify_pdf_signature(frm) {
	frappe.call({
		method:
			"erpnext_moldova_customs.erpnext_moldova_customs.doctype.customs_declaration.customs_declaration.verify_pdf_signature",
		args: { name: frm.doc.name },
		freeze: true,
		callback: (r) => {
			cd_show_signature_dialog(frm, r.message || frm.doc);
			frm.reload_doc();
		},
	});
}

function cd_show_signature_dialog(frm, payload) {
	const evidence = cd_parse_signature_evidence(
		(payload && payload.signature_evidence) || frm.doc.signature_evidence
	);
	const signatures = evidence.signatures || [];
	const filename = cd_signature_filename(frm);
	const dialog = new frappe.ui.Dialog({
		title: __("Signatures for {0}", [filename]),
		size: "large",
		fields: [{ fieldname: "body", fieldtype: "HTML" }],
		primary_action_label: __("Close"),
		primary_action: () => dialog.hide(),
	});
	const $wrap = $(`
		<div class="cd-sig-layout">
			<div class="cd-sig-list"></div>
			<div class="cd-sig-detail"></div>
		</div>
	`);
	dialog.fields_dict.body.$wrapper.empty().append($wrap);
	dialog.$wrapper.addClass("cd-sig-dialog");
	const $list = $wrap.find(".cd-sig-list");
	const $detail = $wrap.find(".cd-sig-detail");
	const all_intact = signatures.length && signatures.every((row) => row.integrity === "Passed");

	function bind_view_pdf() {
		$detail.find(".cd-sig-view-pdf").on("click", () => {
			if (frm.doc.original_file) window.open(frm.doc.original_file, "_blank");
		});
	}

	function set_active(selector) {
		$list.find(".cd-sig-item").removeClass("active");
		$list.find(selector).addClass("active");
	}

	function render_integrity() {
		const headline = all_intact
			? __("The document has not been modified since the signature was applied")
			: __("The document has been modified since the signature was applied");
		$detail.html(`
			<div class="cd-sig-actions">
				<button class="btn btn-sm btn-default cd-sig-view-pdf" type="button">${__("View PDF")}</button>
			</div>
			<div class="form-message ${all_intact ? "green" : "red"}">${frappe.utils.escape_html(headline)}</div>
		`);
		bind_view_pdf();
		set_active('.cd-sig-item[data-idx="integrity"]');
	}

	function render_detail(index) {
		const row = signatures[index] || {};
		const intact = row.integrity === "Passed";
		const headline = intact ? __("Signature is VALID") : __("Signature is INVALID");
		const bullets = [];
		if (intact) {
			bullets.push(__("The document has not been modified since the signature was applied"));
		} else {
			bullets.push(__("The document does not match the signed bytes"));
		}
		if (row.timestamp === "Not Checked") {
			bullets.push(__("Timestamp was not checked"));
		} else if (row.timestamp === "Passed") {
			bullets.push(__("Timestamp is VALID"));
		} else {
			bullets.push(__("Timestamp is INVALID"));
		}
		const meta = [
			[__("Signer"), row.signer_name || "—"],
			[__("Serial Number"), row.serial_number || "—"],
			[__("Organization"), row.organization || "—"],
			[__("Time"), row.time_display || row.declared_time || "—"],
			[__("Reason"), row.reason || "—"],
			[__("Location"), row.location || "—"],
		];
		$detail.html(`
			<div class="cd-sig-actions">
				<button class="btn btn-sm btn-default cd-sig-view-pdf" type="button">${__("View PDF")}</button>
			</div>
			<div class="form-message ${intact ? "green" : "red"}">${frappe.utils.escape_html(headline)}</div>
			<ul class="cd-sig-bullets">
				${bullets.map((item) => `<li>${frappe.utils.escape_html(item)}</li>`).join("")}
			</ul>
			<dl class="cd-sig-meta">
				${meta
					.map(
						([label, value]) => `
					<dt><label class="control-label">${frappe.utils.escape_html(label)}</label></dt>
					<dd><div class="control-value like-disabled-input">${frappe.utils.escape_html(value)}</div></dd>
				`
					)
					.join("")}
			</dl>
		`);
		bind_view_pdf();
		set_active(`.cd-sig-item[data-idx="${index}"]`);
	}

	signatures.forEach((row, index) => {
		const intact = row.integrity === "Passed";
		$list.append(`
			<div class="cd-sig-item" data-idx="${index}">
				${cd_sig_badge(intact)}
				<div class="cd-sig-item-text">
					<div class="cd-sig-item-title">${frappe.utils.escape_html(row.signer_name || row.field || __("Signer {0}", [index + 1]))}</div>
					<div class="cd-sig-item-time">${frappe.utils.escape_html(row.time_display || row.declared_time || "")}</div>
				</div>
			</div>
		`);
	});
	$list.append(`
		<div class="cd-sig-item cd-sig-integrity" data-idx="integrity">
			${cd_sig_badge(all_intact)}
			<div class="cd-sig-item-text">
				<div class="cd-sig-item-title">${
					all_intact ? __("has not been altered") : __("has been altered")
				}</div>
			</div>
		</div>
	`);
	$list.on("click", ".cd-sig-item", function () {
		const idx = $(this).attr("data-idx");
		if (idx === "integrity") {
			render_integrity();
			return;
		}
		render_detail(cint(idx));
	});
	if (!signatures.length) {
		$detail.html(`<p class="text-muted">${__("No embedded PDF signature field")}</p>`);
	} else {
		render_detail(Math.max(0, signatures.length - 1));
	}
	dialog.show();
}
