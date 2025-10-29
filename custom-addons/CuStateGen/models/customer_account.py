from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class CustomerAccount(models.Model):
    _name = 'customer.account'
    _description = 'Customer Account Synced from ERPNext'
    _order = 'name'
    _rec_name = 'customer_name'

    name = fields.Char(string='Customer ID', required=True, index=True)
    customer_name = fields.Char(string='Customer Name', required=True)
    erpnext_customer_id = fields.Char(string='ERPNext ID', required=True, index=True)
    
    # Contact Information
    email = fields.Char(string='Email')
    phone = fields.Char(string='Phone')
    mobile = fields.Char(string='Mobile')
    
    # Address
    billing_address = fields.Text(string='Billing Address')
    shipping_address = fields.Text(string='Shipping Address')
    
    # Financial
    customer_group = fields.Char(string='Customer Group')
    territory = fields.Char(string='Territory')
    credit_limit = fields.Monetary(string='Credit Limit', currency_field='currency_id')
    payment_terms = fields.Char(string='Payment Terms')
    
    # Balances
    outstanding_balance = fields.Monetary(
        string='Outstanding Balance',
        currency_field='currency_id',
        compute='_compute_balances',
        store=True
    )
    total_invoiced = fields.Monetary(
        string='Total Invoiced',
        currency_field='currency_id',
        compute='_compute_balances',
        store=True
    )
    total_paid = fields.Monetary(
        string='Total Paid',
        currency_field='currency_id',
        compute='_compute_balances',
        store=True
    )
    
    # Relationships
    statement_ids = fields.One2many(
        'customer.statement',
        'customer_id',
        string='Statements'
    )
    statement_count = fields.Integer(
        string='Statements',
        compute='_compute_statement_count'
    )
    
    # Sync Info
    last_sync_date = fields.Datetime(string='Last Sync', readonly=True)
    active = fields.Boolean(default=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Analytics
    last_invoice_date = fields.Date(string='Last Invoice', compute='_compute_analytics', store=True)
    last_payment_date = fields.Date(string='Last Payment', compute='_compute_analytics', store=True)
    days_since_last_payment = fields.Integer(
        string='Days Since Payment',
        compute='_compute_analytics',
        store=True
    )

    _sql_constraints = [
        ('erpnext_customer_unique', 'UNIQUE(erpnext_customer_id)', 'ERPNext Customer ID must be unique!')
    ]

    @api.depends('statement_ids')
    def _compute_statement_count(self):
        for record in self:
            record.statement_count = len(record.statement_ids)

    @api.depends('statement_ids.line_ids.amount', 'statement_ids.line_ids.line_type')
    def _compute_balances(self):
        for record in self:
            if not record.statement_ids:
                record.outstanding_balance = 0
                record.total_invoiced = 0
                record.total_paid = 0
                continue
            
            latest_statement = record.statement_ids.sorted('date_to', reverse=True)[:1]
            if latest_statement:
                record.outstanding_balance = latest_statement.closing_balance
                
                # Calculate totals from all statement lines
                all_lines = record.statement_ids.mapped('line_ids')
                record.total_invoiced = sum(
                    line.amount for line in all_lines 
                    if line.line_type == 'invoice'
                )
                record.total_paid = sum(
                    line.amount for line in all_lines 
                    if line.line_type == 'payment'
                )
            else:
                record.outstanding_balance = 0
                record.total_invoiced = 0
                record.total_paid = 0

    @api.depends('statement_ids.line_ids')
    def _compute_analytics(self):
        for record in self:
            all_lines = record.statement_ids.mapped('line_ids')
            
            invoice_lines = all_lines.filtered(lambda l: l.line_type == 'invoice')
            payment_lines = all_lines.filtered(lambda l: l.line_type == 'payment')
            
            record.last_invoice_date = max(
                invoice_lines.mapped('date'), default=False
            )
            record.last_payment_date = max(
                payment_lines.mapped('date'), default=False
            )
            
            if record.last_payment_date:
                record.days_since_last_payment = (
                    fields.Date.today() - record.last_payment_date
                ).days
            else:
                record.days_since_last_payment = 0

    def action_sync_from_erpnext(self):
        """Sync this customer from ERPNext"""
        self.ensure_one()
        
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError('No active ERPNext configuration found.')
        
        import requests
        
        url = f"{config.base_url}/api/resource/Customer/{self.erpnext_customer_id}"
        
        try:
            response = requests.get(url, headers=config._get_headers())
            response.raise_for_status()
            data = response.json().get('data', {})
            
            self.write({
                'customer_name': data.get('customer_name', self.customer_name),
                'email': data.get('email_id'),
                'phone': data.get('phone'),
                'mobile': data.get('mobile_no'),
                'customer_group': data.get('customer_group'),
                'territory': data.get('territory'),
                'credit_limit': data.get('credit_limit', 0),
                'payment_terms': data.get('payment_terms'),
                'last_sync_date': fields.Datetime.now(),
            })
            
            _logger.info(f"Synced customer {self.name} from ERPNext")
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Successful',
                    'message': f'Customer {self.customer_name} synced from ERPNext',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Failed to sync customer: {str(e)}")
            raise UserError(f'Failed to sync from ERPNext: {str(e)}')

    @api.model
    def sync_all_customers_from_erpnext(self):
        """Bulk sync all customers from ERPNext"""
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError('No active ERPNext configuration found.')
        
        import requests
        
        url = f"{config.base_url}/api/resource/Customer"
        params = {'fields': '["name", "customer_name", "email_id", "customer_group"]'}
        
        try:
            response = requests.get(url, headers=config._get_headers(), params=params)
            response.raise_for_status()
            customers = response.json().get('data', [])
            
            created_count = 0
            updated_count = 0
            
            for customer_data in customers:
                existing = self.search([
                    ('erpnext_customer_id', '=', customer_data['name'])
                ])
                
                vals = {
                    'name': customer_data['name'],
                    'customer_name': customer_data.get('customer_name', customer_data['name']),
                    'erpnext_customer_id': customer_data['name'],
                    'email': customer_data.get('email_id'),
                    'customer_group': customer_data.get('customer_group'),
                    'last_sync_date': fields.Datetime.now(),
                }
                
                if existing:
                    existing.write(vals)
                    updated_count += 1
                else:
                    self.create(vals)
                    created_count += 1
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Bulk Sync Complete',
                    'message': f'Created {created_count}, Updated {updated_count} customers',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            _logger.error(f"Bulk sync failed: {str(e)}")
            raise UserError(f'Bulk sync failed: {str(e)}')

    def action_generate_statement(self):
        """Open wizard to generate statement"""
        self.ensure_one()
        
        return {
            'name': 'Generate Statement',
            'type': 'ir.actions.act_window',
            'res_model': 'statement.generator.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_customer_id': self.id,
            }
        }

    def action_view_statements(self):
        """View all statements for this customer"""
        self.ensure_one()
        
        return {
            'name': f'Statements - {self.customer_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.statement',
            'view_mode': 'tree,form',
            'domain': [('customer_id', '=', self.id)],
            'context': {'default_customer_id': self.id}
        }