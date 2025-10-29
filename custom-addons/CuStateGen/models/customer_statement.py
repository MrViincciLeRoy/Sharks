from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class CustomerStatement(models.Model):
    _name = 'customer.statement'
    _description = 'Customer Account Statement'
    _order = 'date_to desc'
    _rec_name = 'statement_number'

    statement_number = fields.Char(
        string='Statement #',
        required=True,
        copy=False,
        readonly=True,
        default='New'
    )
    customer_id = fields.Many2one(
        'customer.account',
        string='Customer',
        required=True,
        ondelete='cascade'
    )
    customer_name = fields.Char(related='customer.id.customer_name', string='Customer Name', store=True)
    
    # Date Range
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True, default=fields.Date.today)
    
    # Balances
    opening_balance = fields.Monetary(
        string='Opening Balance',
        currency_field='currency_id'
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        currency_field='currency_id',
        compute='_compute_closing_balance',
        store=True
    )
    total_invoiced = fields.Monetary(
        string='Total Invoiced',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True
    )
    total_paid = fields.Monetary(
        string='Total Paid',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True
    )
    total_credits = fields.Monetary(
        string='Total Credits',
        currency_field='currency_id',
        compute='_compute_totals',
        store=True
    )
    
    # Lines
    line_ids = fields.One2many(
        'customer.statement.line',
        'statement_id',
        string='Statement Lines'
    )
    line_count = fields.Integer(
        string='Transactions',
        compute='_compute_line_count'
    )
    
    # Aging Analysis
    current_amount = fields.Monetary(string='Current', currency_field='currency_id')
    days_30 = fields.Monetary(string='30 Days', currency_field='currency_id')
    days_60 = fields.Monetary(string='60 Days', currency_field='currency_id')
    days_90 = fields.Monetary(string='90 Days', currency_field='currency_id')
    days_90_plus = fields.Monetary(string='90+ Days', currency_field='currency_id')
    
    # Template & Notes
    template_id = fields.Many2one(
        'statement.template',
        string='Template',
        default=lambda self: self.env['statement.template'].search([], limit=1)
    )
    notes = fields.Text(string='Notes')
    internal_notes = fields.Text(string='Internal Notes')
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('sent', 'Sent'),
        ('paid', 'Paid')
    ], default='draft', string='Status')
    
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    
    # Forecasting
    predicted_payment_date = fields.Date(
        string='Predicted Payment',
        help='AI-predicted payment date from Forecaster module'
    )
    payment_confidence = fields.Float(
        string='Payment Confidence %',
        help='Confidence score from payment prediction'
    )

    @api.model
    def create(self, vals):
        if vals.get('statement_number', 'New') == 'New':
            vals['statement_number'] = self.env['ir.sequence'].next_by_code(
                'customer.statement'
            ) or 'New'
        return super().create(vals)

    @api.depends('line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.line_ids)

    @api.depends('line_ids.amount', 'line_ids.line_type', 'opening_balance')
    def _compute_closing_balance(self):
        for record in self:
            invoices = sum(
                line.amount for line in record.line_ids 
                if line.line_type == 'invoice'
            )
            payments = sum(
                line.amount for line in record.line_ids 
                if line.line_type == 'payment'
            )
            credits = sum(
                line.amount for line in record.line_ids 
                if line.line_type == 'credit'
            )
            
            record.closing_balance = (
                record.opening_balance + invoices - payments - credits
            )

    @api.depends('line_ids.amount', 'line_ids.line_type')
    def _compute_totals(self):
        for record in self:
            record.total_invoiced = sum(
                line.amount for line in record.line_ids 
                if line.line_type == 'invoice'
            )
            record.total_paid = sum(
                line.amount for line in record.line_ids 
                if line.line_type == 'payment'
            )
            record.total_credits = sum(
                line.amount for line in record.line_ids 
                if line.line_type == 'credit'
            )

    def action_fetch_from_erpnext(self):
        """Fetch transactions from ERPNext and populate statement"""
        self.ensure_one()
        
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError('No active ERPNext configuration found.')
        
        import requests
        
        # Fetch Sales Invoices
        self._fetch_invoices(config)
        
        # Fetch Payment Entries
        self._fetch_payments(config)
        
        # Fetch Credit Notes
        self._fetch_credit_notes(config)
        
        # Calculate aging
        self._calculate_aging()
        
        # Try to predict payment date
        self._predict_payment()
        
        self.state = 'generated'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Statement Generated',
                'message': f'Found {self.line_count} transactions',
                'type': 'success',
            }
        }

    def _fetch_invoices(self, config):
        """Fetch sales invoices from ERPNext"""
        import requests
        
        url = f"{config.base_url}/api/resource/Sales Invoice"
        filters = {
            'customer': self.customer_id.erpnext_customer_id,
            'posting_date': ['between', [
                self.date_from.strftime('%Y-%m-%d'),
                self.date_to.strftime('%Y-%m-%d')
            ]],
            'docstatus': 1  # Submitted only
        }
        params = {
            'filters': str(filters),
            'fields': '["name", "posting_date", "grand_total", "outstanding_amount", "due_date"]'
        }
        
        try:
            response = requests.get(url, headers=config._get_headers(), params=params)
            response.raise_for_status()
            invoices = response.json().get('data', [])
            
            for inv in invoices:
                self.env['customer.statement.line'].create({
                    'statement_id': self.id,
                    'date': inv['posting_date'],
                    'line_type': 'invoice',
                    'reference': inv['name'],
                    'description': f"Invoice {inv['name']}",
                    'amount': inv['grand_total'],
                    'outstanding': inv.get('outstanding_amount', 0),
                    'due_date': inv.get('due_date'),
                })
            
            _logger.info(f"Fetched {len(invoices)} invoices for {self.customer_id.name}")
            
        except Exception as e:
            _logger.error(f"Failed to fetch invoices: {str(e)}")
            raise UserError(f'Failed to fetch invoices: {str(e)}')

    def _fetch_payments(self, config):
        """Fetch payment entries from ERPNext"""
        import requests
        
        url = f"{config.base_url}/api/resource/Payment Entry"
        filters = {
            'party': self.customer_id.erpnext_customer_id,
            'posting_date': ['between', [
                self.date_from.strftime('%Y-%m-%d'),
                self.date_to.strftime('%Y-%m-%d')
            ]],
            'docstatus': 1
        }
        params = {
            'filters': str(filters),
            'fields': '["name", "posting_date", "paid_amount", "reference_no"]'
        }
        
        try:
            response = requests.get(url, headers=config._get_headers(), params=params)
            response.raise_for_status()
            payments = response.json().get('data', [])
            
            for pay in payments:
                self.env['customer.statement.line'].create({
                    'statement_id': self.id,
                    'date': pay['posting_date'],
                    'line_type': 'payment',
                    'reference': pay['name'],
                    'description': f"Payment {pay.get('reference_no', pay['name'])}",
                    'amount': pay['paid_amount'],
                })
            
            _logger.info(f"Fetched {len(payments)} payments")
            
        except Exception as e:
            _logger.error(f"Failed to fetch payments: {str(e)}")

    def _fetch_credit_notes(self, config):
        """Fetch credit notes from ERPNext"""
        import requests
        
        url = f"{config.base_url}/api/resource/Sales Invoice"
        filters = {
            'customer': self.customer_id.erpnext_customer_id,
            'is_return': 1,
            'posting_date': ['between', [
                self.date_from.strftime('%Y-%m-%d'),
                self.date_to.strftime('%Y-%m-%d')
            ]],
            'docstatus': 1
        }
        params = {
            'filters': str(filters),
            'fields': '["name", "posting_date", "grand_total"]'
        }
        
        try:
            response = requests.get(url, headers=config._get_headers(), params=params)
            response.raise_for_status()
            credits = response.json().get('data', [])
            
            for cred in credits:
                self.env['customer.statement.line'].create({
                    'statement_id': self.id,
                    'date': cred['posting_date'],
                    'line_type': 'credit',
                    'reference': cred['name'],
                    'description': f"Credit Note {cred['name']}",
                    'amount': abs(cred['grand_total']),
                })
            
        except Exception as e:
            _logger.error(f"Failed to fetch credit notes: {str(e)}")

    def _calculate_aging(self):
        """Calculate aging buckets for outstanding invoices"""
        self.ensure_one()
        
        today = fields.Date.today()
        current = days_30 = days_60 = days_90 = days_90_plus = 0
        
        invoice_lines = self.line_ids.filtered(lambda l: l.line_type == 'invoice' and l.outstanding > 0)
        
        for line in invoice_lines:
            if not line.due_date:
                current += line.outstanding
                continue
            
            days_overdue = (today - line.due_date).days
            
            if days_overdue <= 0:
                current += line.outstanding
            elif days_overdue <= 30:
                days_30 += line.outstanding
            elif days_overdue <= 60:
                days_60 += line.outstanding
            elif days_overdue <= 90:
                days_90 += line.outstanding
            else:
                days_90_plus += line.outstanding
        
        self.write({
            'current_amount': current,
            'days_30': days_30,
            'days_60': days_60,
            'days_90': days_90,
            'days_90_plus': days_90_plus,
        })

    def _predict_payment(self):
        """Use Forecaster module to predict payment date"""
        self.ensure_one()
        
        # Check if Forecaster is installed
        if not self.env['ir.module.module'].search([
            ('name', '=', 'Forecaster'),
            ('state', '=', 'installed')
        ]):
            return
        
        try:
            # Simple prediction based on customer history
            past_statements = self.search([
                ('customer_id', '=', self.customer_id.id),
                ('state', '=', 'paid'),
                ('id', '!=', self.id)
            ], limit=10, order='date_to desc')
            
            if past_statements:
                avg_days = sum(
                    (stmt.closing_balance / stmt.total_invoiced * 30 if stmt.total_invoiced else 0)
                    for stmt in past_statements
                ) / len(past_statements)
                
                from datetime import timedelta
                self.predicted_payment_date = self.date_to + timedelta(days=int(avg_days))
                self.payment_confidence = min(len(past_statements) * 10, 100)
                
        except Exception as e:
            _logger.warning(f"Payment prediction failed: {str(e)}")

    def action_print_statement(self):
        """Generate PDF statement"""
        self.ensure_one()
        return self.env.ref('CuStateGen.action_report_customer_statement').report_action(self)

    def action_send_email(self):
        """Send statement via email"""
        self.ensure_one()
        
        if not self.customer_id.email:
            raise UserError('Customer has no email address configured.')
        
        # Mark as sent
        self.state = 'sent'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'customer.statement',
                'default_res_id': self.id,
                'default_partner_ids': [(4, self.customer_id.id)],
            }
        }