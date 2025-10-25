from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)

class ERPNextConfig(models.Model):
    _name = 'erpnext.config'
    _description = 'ERPNext API Configuration'

    name = fields.Char(string='Configuration Name', required=True)
    base_url = fields.Char(string='ERPNext URL', required=True)
    api_key = fields.Char(string='API Key', required=True)
    api_secret = fields.Char(string='API Secret', required=True)
    active = fields.Boolean(default=True)
    last_sync = fields.Datetime(string='Last Sync', readonly=True)
    
    # Mapping fields
    default_company = fields.Char(string='Default Company', required=True)
    default_cost_center = fields.Char(string='Default Cost Center')
    bank_account = fields.Char(string='Bank Account', required=True, 
                                help='ERPNext bank account name')

    def _get_headers(self):
        """Get API headers with authentication"""
        self.ensure_one()
        return {
            'Authorization': f'token {self.api_key}:{self.api_secret}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def test_connection(self):
        """Test ERPNext connection"""
        self.ensure_one()
        try:
            url = f"{self.base_url}/api/method/frappe.auth.get_logged_user"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Successful',
                    'message': f"Connected as: {response.json().get('message')}",
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Connection test failed: {str(e)}")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Failed',
                    'message': str(e),
                    'type': 'danger',
                }
            }

    def create_journal_entry(self, transaction):
        """Create Journal Entry in ERPNext from bank transaction"""
        self.ensure_one()
        
        # FIXED: Use transaction.date instead of transaction.transaction_date
        posting_date = transaction.date.strftime('%Y-%m-%d')
        
        # Determine debit/credit based on transaction type
        if transaction.transaction_type == 'debit':
            # Money out: Credit bank, Debit expense
            bank_credit = abs(transaction.amount)
            bank_debit = 0
            expense_credit = 0
            expense_debit = abs(transaction.amount)
        else:  # credit
            # Money in: Debit bank, Credit income
            bank_credit = 0
            bank_debit = abs(transaction.amount)
            expense_credit = abs(transaction.amount)
            expense_debit = 0
        
        # Prepare journal entry data
        journal_data = {
            'doctype': 'Journal Entry',
            'company': self.default_company,
            'posting_date': posting_date,
            'accounts': [
                {
                    'account': self.bank_account,
                    'debit_in_account_currency': bank_debit,
                    'credit_in_account_currency': bank_credit,
                },
                {
                    'account': transaction.category_id.erpnext_account,
                    'debit_in_account_currency': expense_debit,
                    'credit_in_account_currency': expense_credit,
                    'cost_center': self.default_cost_center,
                }
            ],
            'user_remark': transaction.description or '',
            'reference_number': transaction.reference or '',
        }
        
        url = f"{self.base_url}/api/resource/Journal Entry"
        
        try:
            response = requests.post(
                url,
                headers=self._get_headers(),
                json=journal_data
            )
            response.raise_for_status()
            result = response.json()
            
            journal_entry_name = result.get('data', {}).get('name')
            
            # Update transaction
            transaction.write({
                'erpnext_synced': True,
                'erpnext_journal_entry': journal_entry_name,
                'erpnext_sync_date': fields.Datetime.now(),
                'erpnext_error': False,
            })
            
            # Log sync
            self.env['erpnext.sync.log'].create({
                'config_id': self.id,
                'record_type': 'bank_transaction',
                'record_id': transaction.id,
                'erpnext_doctype': 'Journal Entry',
                'erpnext_doc_name': journal_entry_name,
                'status': 'success'
            })
            
            _logger.info(f"Successfully synced transaction {transaction.id} to ERPNext: {journal_entry_name}")
            
            return result
            
        except Exception as e:
            error_message = str(e)
            _logger.error(f"Failed to create journal entry: {error_message}")
            
            # Update transaction with error
            transaction.write({
                'erpnext_error': error_message
            })
            
            # Log failure
            self.env['erpnext.sync.log'].create({
                'config_id': self.id,
                'record_type': 'bank_transaction',
                'record_id': transaction.id,
                'status': 'failed',
                'error_message': error_message
            })
            
            raise
