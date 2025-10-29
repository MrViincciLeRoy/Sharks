from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime
from dateutil.relativedelta import relativedelta

class StatementGeneratorWizard(models.TransientModel):
    _name = 'statement.generator.wizard'
    _description = 'Customer Statement Generator Wizard'

    # Customer Selection
    customer_id = fields.Many2one(
        'customer.account',
        string='Customer',
        required=True
    )
    customer_ids = fields.Many2many(
        'customer.account',
        string='Multiple Customers',
        help='Leave empty to generate for single customer'
    )
    generate_for_all = fields.Boolean(
        string='Generate for All Customers',
        help='Generate statements for all active customers'
    )
    
    # Date Range
    date_from = fields.Date(
        string='From Date',
        required=True,
        default=lambda self: fields.Date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='To Date',
        required=True,
        default=fields.Date.today
    )
    period_type = fields.Selection([
        ('custom', 'Custom Range'),
        ('current_month', 'Current Month'),
        ('last_month', 'Last Month'),
        ('current_quarter', 'Current Quarter'),
        ('last_quarter', 'Last Quarter'),
        ('current_year', 'Current Year'),
    ], string='Period', default='current_month')
    
    # Template & Options
    template_id = fields.Many2one(
        'statement.template',
        string='Template',
        default=lambda self: self.env['statement.template'].search([('is_default', '=', True)], limit=1)
    )
    include_opening_balance = fields.Boolean(
        string='Include Opening Balance',
        default=True
    )
    include_aging = fields.Boolean(
        string='Include Aging Analysis',
        default=True
    )
    
    # Actions
    auto_send_email = fields.Boolean(
        string='Auto-send via Email',
        help='Automatically email statements to customers'
    )
    auto_download_pdf = fields.Boolean(
        string='Download PDFs',
        default=True
    )

    @api.onchange('period_type')
    def _onchange_period_type(self):
        """Update date range based on period selection"""
        today = fields.Date.today()
        
        if self.period_type == 'current_month':
            self.date_from = today.replace(day=1)
            self.date_to = today
        elif self.period_type == 'last_month':
            first_of_month = today.replace(day=1)
            last_month_end = first_of_month - relativedelta(days=1)
            self.date_from = last_month_end.replace(day=1)
            self.date_to = last_month_end
        elif self.period_type == 'current_quarter':
            quarter_start_month = ((today.month - 1) // 3) * 3 + 1
            self.date_from = today.replace(month=quarter_start_month, day=1)
            self.date_to = today
        elif self.period_type == 'last_quarter':
            current_quarter_start = ((today.month - 1) // 3) * 3 + 1
            last_quarter_end = today.replace(month=current_quarter_start, day=1) - relativedelta(days=1)
            last_quarter_start_month = ((last_quarter_end.month - 1) // 3) * 3 + 1
            self.date_from = last_quarter_end.replace(month=last_quarter_start_month, day=1)
            self.date_to = last_quarter_end
        elif self.period_type == 'current_year':
            self.date_from = today.replace(month=1, day=1)
            self.date_to = today

    def action_generate_statements(self):
        """Generate customer statements"""
        self.ensure_one()
        
        # Determine which customers to generate for
        if self.generate_for_all:
            customers = self.env['customer.account'].search([('active', '=', True)])
        elif self.customer_ids:
            customers = self.customer_ids
        else:
            customers = self.customer_id
        
        if not customers:
            raise UserError('Please select at least one customer.')
        
        generated_statements = self.env['customer.statement']
        
        for customer in customers:
            # Check for existing statement
            existing = self.env['customer.statement'].search([
                ('customer_id', '=', customer.id),
                ('date_from', '=', self.date_from),
                ('date_to', '=', self.date_to)
            ])
            
            if existing:
                statement = existing[0]
                statement.line_ids.unlink()  # Refresh data
            else:
                statement = self.env['customer.statement'].create({
                    'customer_id': customer.id,
                    'date_from': self.date_from,
                    'date_to': self.date_to,
                    'template_id': self.template_id.id,
                })
            
            # Fetch data from ERPNext
            try:
                statement.action_fetch_from_erpnext()
                generated_statements |= statement
                
                # Auto-send email if requested
                if self.auto_send_email and customer.email:
                    statement.action_send_email()
                    
            except Exception as e:
                # Log error but continue with other customers
                _logger.error(f"Failed to generate statement for {customer.name}: {str(e)}")
                continue
        
        if not generated_statements:
            raise UserError('No statements were generated. Check ERPNext connection.')
        
        # Return action to view generated statements
        action = {
            'name': 'Generated Statements',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.statement',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', generated_statements.ids)],
        }
        
        if len(generated_statements) == 1:
            action['res_id'] = generated_statements.id
            action['view_mode'] = 'form'
        
        # Download PDFs if requested
        if self.auto_download_pdf:
            return self.env.ref('CuStateGen.action_report_customer_statement').report_action(generated_statements)
        
        return action

    def action_preview_statement(self):
        """Preview statement before generating"""
        self.ensure_one()
        
        if not self.customer_id:
            raise UserError('Please select a customer to preview.')
        
        # Create temporary statement (won't be saved)
        temp_statement = self.env['customer.statement'].new({
            'customer_id': self.customer_id.id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'template_id': self.template_id.id,
        })
        
        return {
            'name': 'Statement Preview',
            'type': 'ir.actions.act_window',
            'res_model': 'customer.statement',
            'res_id': temp_statement.id,
            'view_mode': 'form',
            'target': 'new',
        }