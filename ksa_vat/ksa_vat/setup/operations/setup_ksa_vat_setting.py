import frappe
import os
import json
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def after_install():
    """Create default KSA VAT Settings for Saudi companies on fresh installs."""
    make_custom_fields()
    ensure_setup_page()
    ensure_workspace()

    for company in frappe.get_all(
        'Company',
        filters={'country': 'Saudi Arabia'},
        fields=['name', 'abbr']
    ):
        create_default_ksa_vat_setting(company.name, company.abbr)


def create_ksa_vat_setting(self, method):
    """
    On creation of first company. Creates KSA VAT Setting"""
    # Validating if this is the first company for Saudi Arab
    company_list = frappe.get_all('Company', {
        'country': 'Saudi Arabia'
    })

    ksa_vat_setting = frappe.get_all('KSA VAT Setting', {
        'company': self.name
    })

    if len(company_list) == 1 and len(ksa_vat_setting) == 0:
        make_custom_fields()
        create_default_ksa_vat_setting(self.name, self.abbr)


@frappe.whitelist()
def run_setup(company=None):
    make_custom_fields()
    ensure_setup_page()
    ensure_workspace()

    if company:
        company_doc = frappe.get_doc('Company', company)
        create_default_ksa_vat_setting(company_doc.name, company_doc.abbr)
    else:
        after_install()

    frappe.db.commit()
    return get_setup_status(company)


@frappe.whitelist()
def get_setup_status(company=None):
    companies = frappe.get_all(
        'Company',
        filters={'country': 'Saudi Arabia'},
        fields=['name', 'abbr']
    )

    if company:
        companies = [company_doc for company_doc in companies if company_doc.name == company]

    return {
        'companies': [get_company_setup_status(company_doc) for company_doc in companies],
        'qr_code_field': frappe.db.exists('Custom Field', 'Sales Invoice-qr_code') is not None,
        'workspace': frappe.db.exists('Workspace', 'KSA VAT') is not None
    }


def get_company_setup_status(company_doc):
    default_tax_account = get_default_tax_account(company_doc.name, company_doc.abbr)
    setting_name = frappe.db.get_value('KSA VAT Setting', {'company': company_doc.name}, 'name')
    templates = []

    for row in get_setup_rows():
        item_tax_template = get_company_record_name(row['item_tax_template'], company_doc.abbr)
        templates.append({
            'title': row['title'],
            'item_tax_template': item_tax_template,
            'exists': frappe.db.exists('Item Tax Template', item_tax_template) is not None
        })

    return {
        'company': company_doc.name,
        'abbr': company_doc.abbr,
        'default_tax_account': default_tax_account,
        'setting': setting_name,
        'templates': templates
    }


def create_default_ksa_vat_setting(company, company_abbr):
    if frappe.db.exists('KSA VAT Setting', {'company': company}):
        return

    default_tax_account = get_default_tax_account(company, company_abbr)
    if not default_tax_account:
        return

    account_data = get_setup_data()

    ksa_vat_setting = frappe.get_doc({
        'doctype': 'KSA VAT Setting',
        'company': company
    })

    for data in account_data:
        if data['type'] == 'Sales Account':
            for row in data['accounts']:
                item_tax_template, account = get_setting_row_links(
                    row, company, company_abbr, default_tax_account
                )
                if not item_tax_template or not account:
                    continue

                ksa_vat_setting.append('ksa_vat_sales_accounts', {
                    'title': row['title'],
                    'item_tax_template': item_tax_template,
                    'account': account
                })

        elif data['type'] == 'Purchase Account':
            for row in data['accounts']:
                item_tax_template, account = get_setting_row_links(
                    row, company, company_abbr, default_tax_account
                )
                if not item_tax_template or not account:
                    continue

                ksa_vat_setting.append('ksa_vat_purchase_accounts', {
                    'title': row['title'],
                    'item_tax_template': item_tax_template,
                    'account': account
                })

    if not ksa_vat_setting.ksa_vat_sales_accounts and not ksa_vat_setting.ksa_vat_purchase_accounts:
        return

    ksa_vat_setting.save()


def get_company_record_name(record_name, company_abbr):
    return f'{record_name} - {company_abbr}'


def get_setup_data():
    file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ksa_vat_settings.json')
    with open(file_path, 'r') as json_file:
        return json.load(json_file)


def get_setup_rows():
    rows = []
    seen = set()
    for data in get_setup_data():
        for row in data['accounts']:
            if row['item_tax_template'] in seen:
                continue

            seen.add(row['item_tax_template'])
            rows.append(row)

    return rows


def get_setting_row_links(row, company, company_abbr, default_tax_account):
    item_tax_template = ensure_item_tax_template(row, company, company_abbr, default_tax_account)
    if not frappe.db.exists('Item Tax Template', item_tax_template):
        return None, None

    account = get_tax_account(item_tax_template, default_tax_account)
    if not frappe.db.exists('Account', account):
        return None, None

    return item_tax_template, account


def ensure_item_tax_template(row, company, company_abbr, default_tax_account):
    item_tax_template = get_company_record_name(row['item_tax_template'], company_abbr)
    if frappe.db.exists('Item Tax Template', item_tax_template):
        return item_tax_template

    tax_template = frappe.get_doc({
        'doctype': 'Item Tax Template',
        'title': row['item_tax_template'],
        'company': company,
        'taxes': [{
            'tax_type': default_tax_account,
            'tax_rate': row.get('tax_rate', 0)
        }]
    })

    set_zatca_tax_category(tax_template, row.get('zatca_tax_category'))
    tax_template.insert(ignore_permissions=True)
    return tax_template.name


def set_zatca_tax_category(tax_template, tax_category):
    if not tax_category:
        return

    meta = frappe.get_meta('Item Tax Template')
    if meta.has_field('zatca_tax_category'):
        tax_template.zatca_tax_category = tax_category


def get_default_tax_account(company, company_abbr):
    account = frappe.db.get_value('Account', {
        'company': company,
        'account_number': '2300',
        'account_name': 'Duties and Taxes'
    }, 'name')

    if account:
        return account

    account = frappe.db.get_value('Account', {
        'company': company,
        'account_name': 'Duties and Taxes'
    }, 'name')

    if account:
        return account

    return frappe.db.get_value('Account', {
        'name': ['like', f'%Duties and Taxes%{company_abbr}']
    }, 'name')


def get_tax_account(item_tax_template, fallback_account):
    tax_account = frappe.db.get_value(
        'Item Tax Template Detail',
        {'parent': item_tax_template},
        'tax_type'
    )

    if tax_account:
        return tax_account

    return fallback_account


def ensure_workspace():
    workspace_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'workspace', 'ksa_vat', 'ksa_vat.json'
    )
    ensure_standard_doc(workspace_path)


def ensure_setup_page():
    page_path = os.path.join(
        os.path.dirname(__file__), '..', '..', 'page', 'ksa_vat_setup', 'ksa_vat_setup.json'
    )
    ensure_standard_doc(page_path)


def ensure_standard_doc(file_path):
    with open(file_path, 'r') as doc_file:
        doc_data = json.load(doc_file)

    existing_doc = frappe.db.exists(doc_data['doctype'], doc_data['name'])
    if existing_doc:
        doc = frappe.get_doc(doc_data['doctype'], existing_doc)
        doc.update(doc_data)
        doc.save(ignore_permissions=True)
    else:
        frappe.get_doc(doc_data).insert(ignore_permissions=True)

def make_custom_fields():
    if frappe.db.exists('Custom Field', 'Sales Invoice-qr_code'):
        return

    qr_code_field = dict(
        fieldname='qr_code', 
        label='QR Code', 
        fieldtype='Attach Image', 
        read_only=1, no_copy=1, hidden=1)
    
    create_custom_field('Sales Invoice', qr_code_field)
