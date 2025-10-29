from odoo import models, fields, api

class StatementTemplate(models.Model):
    _name = 'statement.template'
    _description = 'Customer Statement Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    is_default = fields.Boolean(string='Default Template')
    
    # Company Branding
    company_logo = fields.Binary(string='Company Logo')
    company_name = fields.Char(string='Company Name', default=lambda self: self.env.company.name)
    company_address = fields.Text(string='Company Address')
    company_phone = fields.Char(string='Phone')
    company_email = fields.Char(string='Email')
    company_website = fields.Char(string='Website')
    
    # Layout Options
    show_logo = fields.Boolean(string='Show Logo', default=True)
    show_aging = fields.Boolean(string='Show Aging Analysis', default=True)
    show_payment_terms = fields.Boolean(string='Show Payment Terms', default=True)
    show_bank_details = fields.Boolean(string='Show Bank Details', default=True)
    
    # Colors
    header_color = fields.Char(string='Header Color', default='#1f77b4')
    accent_color = fields.Char(string='Accent Color', default='#ff7f0e')
    
    # Bank Details
    bank_name = fields.Char(string='Bank Name')
    bank_account_number = fields.Char(string='Account Number')
    bank_branch = fields.Char(string='Branch')
    swift_code = fields.Char(string='SWIFT Code')
    
    # Footer Text
    footer_message = fields.Text(
        string='Footer Message',
        default='Thank you for your business. Please remit payment by the due date.'
    )
    terms_and_conditions = fields.Text(string='Terms & Conditions')
    
    active = fields.Boolean(default=True)

    @api.model
    def create(self, vals):
        # If marked as default, unset other defaults
        if vals.get('is_default'):
            self.search([('is_default', '=', True)]).write({'is_default': False})
        return super().create(vals)

    def write(self, vals):
        # If marked as default, unset other defaults
        if vals.get('is_default'):
            self.search([('is_default', '=', True), ('id', 'not in', self.ids)]).write({'is_default': False})
        return super().write(vals)