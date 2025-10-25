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
    default_company = fields.Char(string='Default Company')
    default_cost_center = fields.Char(string='Default Cost Center')

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

    def get_customers(self):
        """Fetch customers from ERPNext"""
        self.ensure_one()
        url = f"{self.base_url}/api/resource/Customer"
        params = {'fields': '["name","customer_name","customer_type"]'}
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params
            )
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception as e:
            _logger.error(f"Failed to fetch customers: {str(e)}")
            raise

    def create_journal_entry(self, transaction):
        """Create Journal Entry in ERPNext from bank transaction"""
        self.ensure_one()
        
        # Prepare journal entry data
        journal_data = {
            'doctype': 'Journal Entry',
            'company': self.default_company,
            'posting_date': transaction.transaction_date.strftime('%Y-%m-%d'),
            'accounts': [
                {
                    'account': 'Bank Account - Company',  # Configure this
                    'debit_in_account_currency': abs(transaction.amount) if transaction.amount > 0 else 0,
                    'credit_in_account_currency': abs(transaction.amount) if transaction.amount < 0 else 0,
                },
                {
                    'account': transaction.category_id.erpnext_account or 'Expenses - Company',
                    'debit_in_account_currency': abs(transaction.amount) if transaction.amount < 0 else 0,
                    'credit_in_account_currency': abs(transaction.amount) if transaction.amount > 0 else 0,
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
            
            # Update transaction
            transaction.write({
                'erpnext_synced': True,
                'erpnext_journal_entry': result.get('data', {}).get('name'),
                'state': 'synced'
            })
            
            # Log sync
            self.env['erpnext.sync.log'].create({
                'config_id': self.id,
                'record_type': 'bank_transaction',
                'record_id': transaction.id,
                'erpnext_doctype': 'Journal Entry',
                'erpnext_doc_name': result.get('data', {}).get('name'),
                'status': 'success'
            })
            
            return result
            
        except Exception as e:
            _logger.error(f"Failed to create journal entry: {str(e)}")
            # Log failure
            self.env['erpnext.sync.log'].create({
                'config_id': self.id,
                'record_type': 'bank_transaction',
                'record_id': transaction.id,
                'status': 'failed',
                'error_message': str(e)
            })
            raise

    def sync_all_uncategorized_transactions(self):
        """Sync all categorized but unsynced transactions"""
        self.ensure_one()
        transactions = self.env['bank.transaction'].search([
            ('is_categorized', '=', True),
            ('erpnext_synced', '=', False)
        ])
        
        success_count = 0
        for trans in transactions:
            try:
                self.create_journal_entry(trans)
                success_count += 1
            except Exception as e:
                _logger.error(f"Failed to sync transaction {trans.id}: {str(e)}")
                continue
        
        self.last_sync = fields.Datetime.now()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Complete',
                'message': f'Synced {success_count} of {len(transactions)} transactions',
                'type': 'success',
            }
        }