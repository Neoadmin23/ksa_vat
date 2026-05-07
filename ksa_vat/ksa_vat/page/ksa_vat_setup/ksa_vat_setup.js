frappe.pages["ksa-vat-setup"].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: __("KSA VAT Setup"),
		single_column: true
	});

	new KSAVATSetup(wrapper);
};

class KSAVATSetup {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.page = wrapper.page;
		this.body = $('<div class="ksa-vat-setup"></div>').appendTo(this.wrapper.find(".layout-main-section"));
		this.setup_style();
		this.render();
		this.load_status();
	}

	setup_style() {
		frappe.dom.set_style(`
			.ksa-vat-setup { max-width: 1100px; padding: 20px; }
			.ksa-vat-toolbar { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 18px; flex-wrap: wrap; }
			.ksa-vat-company { min-width: 320px; }
			.ksa-vat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-bottom: 18px; }
			.ksa-vat-card { border: 1px solid var(--border-color); border-radius: 8px; padding: 14px; background: var(--card-bg); }
			.ksa-vat-card h4 { font-size: 14px; margin: 0 0 8px; }
			.ksa-vat-muted { color: var(--text-muted); font-size: 12px; }
			.ksa-vat-status { display: inline-flex; align-items: center; border-radius: 999px; padding: 2px 8px; font-size: 12px; font-weight: 600; }
			.ksa-vat-ok { background: #eaf8ef; color: #16794c; }
			.ksa-vat-warn { background: #fff4d6; color: #8a5a00; }
			.ksa-vat-table { width: 100%; border-collapse: collapse; margin-top: 8px; font-size: 13px; }
			.ksa-vat-table th, .ksa-vat-table td { border-bottom: 1px solid var(--border-color); padding: 8px; text-align: left; }
			.ksa-vat-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
		`);
	}

	render() {
		this.body.html(`
			<div class="ksa-vat-toolbar">
				<div class="ksa-vat-company"></div>
				<button class="btn btn-primary ksa-vat-run">${__("Create or Repair Setup")}</button>
				<button class="btn btn-default ksa-vat-refresh">${__("Refresh")}</button>
			</div>
			<div class="ksa-vat-grid">
				<div class="ksa-vat-card">
					<h4>${__("VAT Account Review")}</h4>
					<div class="ksa-vat-account ksa-vat-muted">${__("Loading")}</div>
				</div>
				<div class="ksa-vat-card">
					<h4>${__("Invoice QR Code")}</h4>
					<div class="ksa-vat-qr ksa-vat-muted">${__("Loading")}</div>
				</div>
				<div class="ksa-vat-card">
					<h4>${__("Workspace")}</h4>
					<div class="ksa-vat-workspace ksa-vat-muted">${__("Loading")}</div>
				</div>
			</div>
			<div class="ksa-vat-card">
				<h4>${__("Company VAT Setup")}</h4>
				<div class="ksa-vat-summary ksa-vat-muted">${__("Loading")}</div>
			</div>
		`);

		this.company_field = frappe.ui.form.make_control({
			parent: this.body.find(".ksa-vat-company"),
			df: {
				fieldtype: "Link",
				options: "Company",
				fieldname: "company",
				label: __("Company"),
				get_query: () => ({ filters: { country: "Saudi Arabia" } })
			},
			render_input: true
		});

		this.body.find(".ksa-vat-run").on("click", () => this.run_setup());
		this.body.find(".ksa-vat-refresh").on("click", () => this.load_status());
	}

	load_status() {
		frappe.call({
			method: "ksa_vat.ksa_vat.setup.operations.setup_ksa_vat_setting.get_setup_status",
			args: { company: this.company_field.get_value() },
			callback: (r) => {
				this.status = r.message || {};
				this.render_status();
			}
		});
	}

	run_setup() {
		frappe.call({
			method: "ksa_vat.ksa_vat.setup.operations.setup_ksa_vat_setting.run_setup",
			args: { company: this.company_field.get_value() },
			freeze: true,
			freeze_message: __("Creating KSA VAT setup"),
			callback: (r) => {
				this.status = r.message || {};
				this.render_status();
				frappe.show_alert({ message: __("KSA VAT setup checked"), indicator: "green" });
			}
		});
	}

	render_status() {
		const companies = this.status.companies || [];
		const company = companies[0];

		this.body.find(".ksa-vat-qr").html(this.badge(this.status.qr_code_field) + " " + __("Sales Invoice QR field"));
		this.body.find(".ksa-vat-workspace").html(this.badge(this.status.workspace) + " " + __("KSA VAT workspace"));

		if (!company) {
			this.body.find(".ksa-vat-account").text(__("No Saudi Arabia company found."));
			this.body.find(".ksa-vat-summary").text(__("Select or create a Saudi Arabia company first."));
			return;
		}

		this.body.find(".ksa-vat-account").html(
			company.default_tax_account
				? `${this.badge(true)} ${frappe.utils.escape_html(company.default_tax_account)}`
				: `${this.badge(false)} ${__("Duties and Taxes account not found")}`
		);

		const rows = (company.templates || []).map((row) => `
			<tr>
				<td>${frappe.utils.escape_html(row.title)}</td>
				<td>${frappe.utils.escape_html(row.item_tax_template)}</td>
				<td>${this.badge(row.exists)}</td>
			</tr>
		`).join("");

		this.body.find(".ksa-vat-summary").html(`
			<div><b>${frappe.utils.escape_html(company.company)}</b> (${frappe.utils.escape_html(company.abbr)})</div>
			<div class="ksa-vat-muted">${__("KSA VAT Setting")}: ${company.setting ? frappe.utils.escape_html(company.setting) : __("Not created")}</div>
			<table class="ksa-vat-table">
				<thead><tr><th>${__("Purpose")}</th><th>${__("Item Tax Template")}</th><th>${__("Status")}</th></tr></thead>
				<tbody>${rows}</tbody>
			</table>
			<div class="ksa-vat-actions">
				<button class="btn btn-default btn-sm" onclick="frappe.set_route('List', 'KSA VAT Setting')">${__("Open KSA VAT Setting")}</button>
				<button class="btn btn-default btn-sm" onclick="frappe.set_route('List', 'Item Tax Template')">${__("Open Item Tax Template")}</button>
				<button class="btn btn-default btn-sm" onclick="frappe.set_route('Tree', 'Account')">${__("Review Chart of Accounts")}</button>
			</div>
		`);
	}

	badge(ok) {
		return `<span class="ksa-vat-status ${ok ? "ksa-vat-ok" : "ksa-vat-warn"}">${ok ? __("Ready") : __("Needs Review")}</span>`;
	}
}
