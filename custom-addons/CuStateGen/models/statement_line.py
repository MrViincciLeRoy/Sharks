from odoo import models, fields, api

class CustomerStatementLine(models.Model):
    _name = 'customer.statement.line'
    _description = 'Customer Statement Line'
    _order = 'date, id'

    statement_id = fields.Many2one(
        'customer.statement',
        string='Statement',
        required=True,
        ondelete='cascade'
    )
    date = fields.Date(string='Date', required=True)
    line_type = fields.Selection([
        ('invoice', 'Invoice'),
        ('payment', 'Payment'),
        ('credit', 'Credit Note'),
        ('adjustment', 'Adjustment')
    ], string='Type', required=True)
    reference = fields.Char(string='Reference')
    description = fields.Text(string='Description', required=True)
    
    # Amounts
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True
    )
    outstanding = fields.Monetary(
        string='Outstanding',
        currency_field='currency_id',
        help='For invoices: remaining unpaid amount'
    )
    running_balance = fields.Monetary(
        string='Balance',
        currency_field='currency_id',
        compute='_compute_running_balance',
        store=True
    )
    
    # Invoice specific
    due_date = fields.Date(string='Due Date')
    days_overdue = fields.Integer(
        string='Days Overdue',
        compute='_compute_days_overdue',
        store=True
    )
    
    # Linking
    erpnext_doctype = fields.Char(string='ERPNext DocType')
    erpnext_doc_name = fields.Char(string='ERPNext Doc Name')
    
    currency_id = fields.Many2one(
        'res.currency',
        related='statement_id.currency_id',
        store=True
    )

    @api.depends('due_date')
    def _compute_days_overdue(self):
        today = fields.Date.today()
        for record in self:
            if record.due_date and record.due_date < today:
                record.days_overdue = (today - record.due_date).days
            else:
                record.days_overdue = 0

    @api.depends('statement_id.line_ids', 'amount', 'line_type', 'statement_id.opening_balance')
    def _compute_running_balance(self):
        """Calculate running balance for each line"""
        for statement in self.mapped('statement_id'):
            balance = statement.opening_balance or 0
            
            for line in statement.line_ids.sorted('date'):
                if line.line_type == 'invoice':
                    balance += line.amount
                elif line.line_type in ('payment', 'credit', 'adjustment'):
                    balance -= line.amount
                
                line.running_balance = balance
    
    def action_view_erpnext_document(self):
        """Open ERPNext document in browser"""
        self.ensure_one()
        
        if not self.erpnext_doc_name or not self.erpnext_doctype:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No ERPNext Link',
                    'message': 'This transaction is not linked to an ERPNext document',
                    'type': 'warning',
                }
            }
        
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Configuration Error',
                    'message': 'No active ERPNext configuration found',
                    'type': 'danger',
                }
            }
        
        url = f"{config.base_url}/app/{self.erpnext_doctype.lower().replace(' ', '-')}/{self.erpnext_doc_name}"
        
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }