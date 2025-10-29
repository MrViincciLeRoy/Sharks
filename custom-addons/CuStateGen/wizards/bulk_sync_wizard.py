from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class BulkSyncWizard(models.TransientModel):
    _name = 'bulk.sync.wizard'
    _description = 'Bulk Sync Customers from ERPNext'

    sync_type = fields.Selection([
        ('customers', 'Sync Customers'),
        ('statements', 'Generate Statements'),
        ('materials', 'Analyze Materials'),
    ], string='Sync Type', default='customers', required=True)
    
    # Customer Sync Options
    sync_all_customers = fields.Boolean(
        string='Sync All Customers',
        default=True
    )
    customer_group_filter = fields.Char(
        string='Filter by Customer Group',
        help='Only sync customers from this group'
    )
    
    # Statement Options
    date_from = fields.Date(string='From Date')
    date_to = fields.Date(string='To Date', default=fields.Date.today)
    
    # Material Analysis Options
    analysis_period_months = fields.Integer(
        string='Analysis Period (Months)',
        default=6
    )
    
    # Progress Tracking
    progress_log = fields.Text(string='Progress Log', readonly=True)

    def action_start_sync(self):
        """Start the bulk sync process"""
        self.ensure_one()
        
        if self.sync_type == 'customers':
            return self._sync_customers()
        elif self.sync_type == 'statements':
            return self._generate_statements()
        elif self.sync_type == 'materials':
            return self._analyze_materials()

    def _sync_customers(self):
        """Bulk sync all customers from ERPNext"""
        self.ensure_one()
        
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError('No active ERPNext configuration found.')
        
        import requests
        
        url = f"{config.base_url}/api/resource/Customer"
        params = {
            'fields': '["name", "customer_name", "email_id", "customer_group", "territory"]',
            'limit_page_length': 0  # Get all
        }
        
        # Apply filter if specified
        if self.customer_group_filter:
            params['filters'] = f'{{"customer_group": "{self.customer_group_filter}"}}'
        
        try:
            response = requests.get(url, headers=config._get_headers(), params=params)
            response.raise_for_status()
            customers = response.json().get('data', [])
            
            created = 0
            updated = 0
            errors = 0
            
            for customer_data in customers:
                try:
                    existing = self.env['customer.account'].search([
                        ('erpnext_customer_id', '=', customer_data['name'])
                    ])
                    
                    vals = {
                        'name': customer_data['name'],
                        'customer_name': customer_data.get('customer_name', customer_data['name']),
                        'erpnext_customer_id': customer_data['name'],
                        'email': customer_data.get('email_id'),
                        'customer_group': customer_data.get('customer_group'),
                        'territory': customer_data.get('territory'),
                        'last_sync_date': fields.Datetime.now(),
                    }
                    
                    if existing:
                        existing.write(vals)
                        updated += 1
                    else:
                        self.env['customer.account'].create(vals)
                        created += 1
                        
                except Exception as e:
                    _logger.error(f"Failed to sync customer {customer_data.get('name')}: {str(e)}")
                    errors += 1
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Customer Sync Complete',
                    'message': f'Created: {created}, Updated: {updated}, Errors: {errors}',
                    'type': 'success' if errors == 0 else 'warning',
                }
            }
            
        except Exception as e:
            _logger.error(f"Bulk customer sync failed: {str(e)}")
            raise UserError(f'Sync failed: {str(e)}')

    def _generate_statements(self):
        """Bulk generate statements for all customers"""
        self.ensure_one()
        
        if not self.date_from or not self.date_to:
            raise UserError('Please specify date range for statements.')
        
        # Get all active customers
        customers = self.env['customer.account'].search([('active', '=', True)])
        
        if not customers:
            raise UserError('No customers found. Please sync customers first.')
        
        generated = 0
        failed = 0
        
        for customer in customers:
            try:
                # Check for existing statement
                existing = self.env['customer.statement'].search([
                    ('customer_id', '=', customer.id),
                    ('date_from', '=', self.date_from),
                    ('date_to', '=', self.date_to)
                ])
                
                if existing:
                    statement = existing[0]
                    statement.line_ids.unlink()
                else:
                    statement = self.env['customer.statement'].create({
                        'customer_id': customer.id,
                        'date_from': self.date_from,
                        'date_to': self.date_to,
                    })
                
                statement.action_fetch_from_erpnext()
                generated += 1
                
            except Exception as e:
                _logger.error(f"Failed for {customer.name}: {str(e)}")
                failed += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk Generation Complete',
                'message': f'Generated: {generated}, Failed: {failed}',
                'type': 'success' if failed == 0 else 'warning',
            }
        }

    def _analyze_materials(self):
        """Bulk material analysis"""
        self.ensure_one()
        
        from dateutil.relativedelta import relativedelta
        
        date_to = fields.Date.today()
        date_from = date_to - relativedelta(months=self.analysis_period_months)
        
        # Create analysis record
        analysis = self.env['material.analysis'].create({
            'name': f'Material Analysis - {fields.Date.today()}',
            'date_from': date_from,
            'date_to': date_to,
        })
        
        try:
            analysis.action_analyze_materials()
            
            return {
                'name': 'Material Analysis',
                'type': 'ir.actions.act_window',
                'res_model': 'material.analysis',
                'res_id': analysis.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except Exception as e:
            _logger.error(f"Material analysis failed: {str(e)}")
            raise UserError(f'Analysis failed: {str(e)}')