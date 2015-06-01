# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, json
from frappe.website.website_generator import WebsiteGenerator
from frappe import _
from frappe.utils.file_manager import save_file, remove_file_by_url
from frappe.website.utils import get_comment_list
from frappe.templates.pages.list import get_context as get_list_context

class WebForm(WebsiteGenerator):
	website = frappe._dict(
		template = "templates/generators/web_form.html",
		condition_field = "published",
		page_title_field = "title",
		no_cache = 1
	)

	def get_context(self, context):
		context.params = frappe.form_dict
		if self.login_required and frappe.session.user != "Guest":
			if self.allow_edit:
				if self.allow_multiple:
					if not context.params.name:
						frappe.form_dict.doctype = self.doc_type
						get_list_context(context)
						context.is_list = True
				else:
					name = frappe.db.get_value(self.doc_type, {"owner": frappe.session.user},
						"name")
					if name:
						frappe.form_dict.name = name

		if frappe.form_dict.name:
			context.layout = self.get_layout()
			context.doc = frappe.get_doc(self.doc_type, frappe.form_dict.name)
			context.title = context.doc.get(context.doc.meta.get_title_field())
			context.parents = [{"name": self.get_route(), "title": self.title }]

		context.comment_doctype = context.doc.doctype
		context.comment_docname = context.doc.name

		if self.allow_comments:
			context.comment_list = get_comment_list(context.doc.doctype, context.doc.name)

		context.types = [f.fieldtype for f in self.web_form_fields]
		return context

	def get_layout(self):
		layout = []
		for df in self.web_form_fields:
			if df.fieldtype=="Section Break" or not layout:
				layout.append([])

			if df.fieldtype=="Column Break" or not layout[-1]:
				layout[-1].append([])

			if df.fieldtype not in ("Section Break", "Column Break"):
				layout[-1][-1].append(df)

		return layout

	def get_parents(self, context):
		if context.parents:
			return context.parents
		elif self.breadcrumbs:
			return json.loads(self.breadcrumbs)

@frappe.whitelist(allow_guest=True)
def accept():
	args = frappe.form_dict
	files = []

	web_form = frappe.get_doc("Web Form", args.web_form)
	if args.doctype != web_form.doc_type:
		frappe.throw(_("Invalid Request"))

	if args.name:
		# update
		doc = frappe.get_doc(args.doctype, args.name)
	else:
		# insert
		doc = frappe.new_doc(args.doctype)

	# set values
	for fieldname, value in args.iteritems():
		if fieldname not in ("web_form", "cmd", "owner"):
			if value and value.startswith("{"):
				try:
					filedata = json.loads(value)
					if "__file_attachment" in filedata:
						files.append((fieldname, filedata))
						continue

				except ValueError:
					pass

			doc.set(fieldname, value)

	if args.name:
		if doc.owner==frappe.session.user:
			doc.save(ignore_permissions=True)
		else:
			# only if permissions are present
			doc.save()

	else:
		# insert
		if web_form.login_required and frappe.session.user=="Guest":
			frappe.throw(_("You must login to submit this form"))

		doc.insert(ignore_permissions = True)

	# add files
	if files:
		for f in files:
			fieldname, filedata = f

			# remove earlier attachmed file (if exists)
			if doc.get(fieldname):
				remove_file_by_url(doc.get(fieldname), doc.doctype, doc.name)

			# save new file
			filedoc = save_file(filedata["filename"], filedata["dataurl"],
				doc.doctype, doc.name, decode=True)

			# update values
			doc.set(fieldname, filedoc.file_url)

		doc.save()

@frappe.whitelist()
def delete(web_form, name):
	web_form = frappe.get_doc("Web Form", web_form)

	owner = frappe.db.get_value(web_form.doc_type, name, "owner")
	if frappe.session.user == owner and web_form.allow_delete:
		frappe.delete_doc(web_form.doc_type, name, ignore_permissions=True)
	else:
		raise frappe.PermissionError, "Not Allowed"
