frappe.provide("erpnext_moldova_customs.cd");

erpnext_moldova_customs.cd.import_pdf = function () {
	frappe.prompt(
		[
			{
				fieldname: "company",
				fieldtype: "Link",
				options: "Company",
				label: __("Company"),
				reqd: 1,
				default: frappe.defaults.get_user_default("Company"),
			},
		],
		({ company }) => {
			const uploader = new frappe.ui.FileUploader({
				allow_multiple: false,
				make_attachments_public: false,
				allow_toggle_optimize: false,
				method: "erpnext_moldova_customs.erpnext_moldova_customs.doctype.customs_declaration.customs_declaration.save_uploaded_original",
				restrictions: {
					allowed_file_types: [".pdf"],
					max_file_size: 15 * 1024 * 1024,
				},
				on_success(file) {
					frappe.call({
						method: "erpnext_moldova_customs.erpnext_moldova_customs.doctype.customs_declaration.customs_declaration.import_pdf",
						args: { file_url: file.file_url, company },
						timeout: 300,
						freeze: true,
						freeze_message: __("Reading SAD…"),
						callback: (r) =>
							r.message && frappe.set_route("Form", "Customs Declaration", r.message),
					});
				},
			});
			const upload_files = uploader.upload_files.bind(uploader);
			uploader.upload_files = () => {
				(uploader.uploader.files || []).forEach((file) => {
					file.optimize = false;
				});
				return upload_files();
			};
		},
		__("Import SAD PDF"),
		__("Upload Document")
	);
};

erpnext_moldova_customs.cd.bind_import_buttons = function (add_button) {
	add_button(__("Import SAD PDF"), erpnext_moldova_customs.cd.import_pdf);
};
