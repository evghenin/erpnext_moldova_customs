frappe.listview_settings["Customs Declaration"] = {
	onload(listview) {
		cd_bind_list_import(listview);
	},
	refresh(listview) {
		cd_bind_list_import(listview);
	},
};

function cd_bind_list_import(listview) {
	if (listview._cd_import_bound || !listview.can_create) {
		return;
	}
	const bind = () => {
		const cd = frappe.provide("erpnext_moldova_customs.cd");
		if (!cd.bind_import_buttons) {
			return false;
		}
		cd.bind_import_buttons((label, action) => {
			listview.page.add_inner_button(label, action);
		});
		listview._cd_import_bound = true;
		return true;
	};
	if (bind()) {
		return;
	}
	frappe.require("/assets/erpnext_moldova_customs/js/customs_declaration_import.js", () => {
		bind();
	});
}
