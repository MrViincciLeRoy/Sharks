from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class BankTransactionExtended(models.Model):
    _inherit = 'bank.transaction'

    # ERPNext Integration Fields
    category_id = fields.Many2one(
        'transaction.category',
        string='Category',
        help='Transaction category for ERPNext mapping'
    )
    is_categorized = fields.Boolean(
        string='Categorized',
        compute='_compute_is_categorized',
        store=True
    )
    erpnext_synced = fields.Boolean(
        string='Synced to ERPNext',
        default=False,
        readonly=True
    )
    erpnext_journal_entry = fields.Char(
        string='ERPNext Journal Entry',
        readonly=True,
        help='Reference to the Journal Entry created in ERPNext'
    )
    erpnext_sync_date = fields.Datetime(
        string='Sync Date',
        readonly=True
    )
    erpnext_error = fields.Text(
        string='Sync Error',
        readonly=True
    )

    @api.depends('category_id')
    def _compute_is_categorized(self):
        for record in self:
            record.is_categorized = bool(record.category_id)

    def action_auto_categorize(self):
        """Automatically categorize based on description"""
        for record in self:
            if not record.category_id:
                category = self.env['transaction.category'].auto_categorize_transaction(
                    record.description
                )
                if category:
                    record.category_id = category
                    _logger.info(f"Auto-categorized transaction {record.id} as {category.name}")

    def action_sync_to_erpnext(self):
        """Sync single transaction to ERPNext"""
        self.ensure_one()
        
        if not self.category_id:
            raise UserError('Please categorize this transaction before syncing to ERPNext.')
        
        if self.erpnext_synced:
            raise UserError('This transaction has already been synced to ERPNext.')
        
        # Get active ERPNext configuration
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError('No active ERPNext configuration found. Please configure ERPNext connection first.')
        
        try:
            result = config.create_journal_entry(self)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sync Successful',
                    'message': f'Transaction synced to ERPNext: {self.erpnext_journal_entry}',
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Failed to sync transaction {self.id}: {str(e)}")
            self.erpnext_error = str(e)
            raise UserError(f'Failed to sync to ERPNext: {str(e)}')

    @api.model
    def action_bulk_auto_categorize(self):
        """Bulk auto-categorize all uncategorized transactions"""
        uncategorized = self.search([
            ('category_id', '=', False),
            ('erpnext_synced', '=', False)
        ])
        
        categorized_count = 0
        for transaction in uncategorized:
            category = self.env['transaction.category'].auto_categorize_transaction(
                transaction.description
            )
            if category:
                transaction.category_id = category
                categorized_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Auto-Categorization Complete',
                'message': f'Categorized {categorized_count} of {len(uncategorized)} transactions',
                'type': 'success',
            }
        }

    @api.model
    def action_bulk_sync_to_erpnext(self):
        """Bulk sync all categorized but unsynced transactions"""
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError('No active ERPNext configuration found.')
        
        transactions = self.search([
            ('is_categorized', '=', True),
            ('erpnext_synced', '=', False)
        ])
        
        if not transactions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Transactions to Sync',
                    'message': 'All categorized transactions are already synced.',
                    'type': 'warning',
                }
            }
        
        success_count = 0
        failed_count = 0
        
        for trans in transactions:
            try:
                config.create_journal_entry(trans)
                success_count += 1
            except Exception as e:
                _logger.error(f"Failed to sync transaction {trans.id}: {str(e)}")
                trans.erpnext_error = str(e)
                failed_count += 1
                continue
        
        message = f'Successfully synced {success_count} transactions.'
        if failed_count > 0:
            message += f' {failed_count} failed.'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk Sync Complete',
                'message': message,
                'type': 'success' if failed_count == 0 else 'warning',
            }
        }
