import frappe
import os
import json
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def after_install():
    """Create default KSA VAT Settings for Saudi companies on fresh installs."""
    make_custom_fields()

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


def create_default_ksa_vat_setting(company, company_abbr):
    if frappe.db.exists('KSA VAT Setting', {'company': company}):
        return

    file_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ksa_vat_settings.json')
    with open(file_path, 'r') as json_file:
        account_data = json.load(json_file)

    ksa_vat_setting = frappe.get_doc({
        'doctype': 'KSA VAT Setting',
        'company': company
    })

    for data in account_data:
        if data['type'] == 'Sales Account':
            for row in data['accounts']:
                item_tax_template, account = get_setting_row_links(row, company_abbr)
                if not item_tax_template or not account:
                    continue

                ksa_vat_setting.append('ksa_vat_sales_accounts', {
                    'title': row['title'],
                    'item_tax_template': item_tax_template,
                    'account': account
                })

        elif data['type'] == 'Purchase Account':
            for row in data['accounts']:
                item_tax_template, account = get_setting_row_links(row, company_abbr)
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


def get_setting_row_links(row, company_abbr):
    item_tax_template = get_company_record_name(row['item_tax_template'], company_abbr)
    if not frappe.db.exists('Item Tax Template', item_tax_template):
        return None, None

    account = get_tax_account(item_tax_template, row['account'], company_abbr)
    if not frappe.db.exists('Account', account):
        return None, None

    return item_tax_template, account


def get_tax_account(item_tax_template, fallback_account, company_abbr):
    tax_account = frappe.db.get_value(
        'Item Tax Template Detail',
        {'parent': item_tax_template},
        'tax_type'
    )

    if tax_account:
        return tax_account

    return get_company_record_name(fallback_account, company_abbr)

def make_custom_fields():
    if frappe.db.exists('Custom Field', 'Sales Invoice-qr_code'):
        return

    qr_code_field = dict(
        fieldname='qr_code', 
        label='QR Code', 
        fieldtype='Attach Image', 
        read_only=1, no_copy=1, hidden=1)
    
    create_custom_field('Sales Invoice', qr_code_field)
