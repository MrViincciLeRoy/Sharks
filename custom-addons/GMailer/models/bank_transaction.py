from odoo import models, fields, api

class BankTransaction(models.Model):
    _name = 'bank.transaction'
    _description = 'Bank Transaction'
    _order = 'date desc'

    name = fields.Char(string='Reference', compute='_compute_name', store=True)
    statement_id = fields.Many2one('email.statement', string='Statement', required=True, ondelete='cascade')
    date = fields.Date(string='Date', required=True)
    description = fields.Text(string='Description', required=True)
    amount = fields.Monetary(string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    transaction_type = fields.Selection([
        ('credit', 'Credit'),
        ('debit', 'Debit'),
    ], string='Type', required=True)
    reference = fields.Char(string='Reference')
    partner_id = fields.Many2one('res.partner', string='Partner')
    account_move_id = fields.Many2one('account.move', string='Journal Entry')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('matched', 'Matched'),
        ('posted', 'Posted'),
    ], default='draft', string='Status')
    
    @api.depends('date', 'description')
    def _compute_name(self):
        for record in self:
            # FIX: Handle case where description might be empty/False
            if record.description and record.date:
                record.name = f"{record.date} - {record.description[:50]}"
            elif record.date:
                record.name = str(record.date)
            else:
                record.name = "New Transaction"
    
    def action_create_journal_entry(self):
        """Create accounting journal entry from transaction"""
        for record in self:
            if record.account_move_id:
                continue
            
            # Get default accounts (customize based on your needs)
            bank_account = self.env['account.account'].search([
                ('user_type_id.type', '=', 'liquidity')
            ], limit=1)
            
            if not bank_account:
                from odoo.exceptions import UserError
                raise UserError('No bank account found. Please configure a liquidity account first.')
            
            # Get default journal
            bank_journal = self.env['account.journal'].search([('type', '=', 'bank')], limit=1)
            
            if not bank_journal:
                from odoo.exceptions import UserError
                raise UserError('No bank journal found. Please create a bank journal first.')
            
            # Create journal entry
            move = self.env['account.move'].create({
                'date': record.date,
                'journal_id': bank_journal.id,
                'ref': record.reference or record.name,
                'line_ids': [
                    (0, 0, {
                        'name': record.description,
                        'account_id': bank_account.id,
                        'debit': record.amount if record.transaction_type == 'credit' else 0,
                        'credit': abs(record.amount) if record.transaction_type == 'debit' else 0,
                        'partner_id': record.partner_id.id if record.partner_id else False,
                    }),
                    # Add corresponding line (expense/income account)
                    # TODO: Add logic to determine the correct offsetting account
                ],
            })
            
            record.write({
                'account_move_id': move.id,
                'state': 'posted',
            })