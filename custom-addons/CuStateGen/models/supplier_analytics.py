from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class SupplierAnalytics(models.Model):
    _name = 'supplier.analytics'
    _description = 'Supplier Purchase Analytics'
    _order = 'total_purchase_value desc'

    name = fields.Char(string='Supplier Name', required=True)
    supplier_code = fields.Char(string='Supplier Code')
    erpnext_supplier_id = fields.Char(string='ERPNext ID', index=True)
    
    # Date Range
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    
    # Purchase Summary
    total_purchase_value = fields.Monetary(
        string='Total Purchase Value',
        currency_field='currency_id'
    )
    total_invoices = fields.Integer(string='Total Invoices')
    total_materials = fields.Integer(string='Unique Materials')
    avg_invoice_value = fields.Monetary(
        string='Avg Invoice Value',
        currency_field='currency_id',
        compute='_compute_averages',
        store=True
    )
    
    # Performance Metrics
    on_time_delivery_rate = fields.Float(
        string='On-Time Delivery %',
        digits=(5, 2)
    )
    quality_rating = fields.Float(
        string='Quality Rating',
        digits=(3, 1),
        help='Rating out of 5'
    )
    price_competitiveness = fields.Selection([
        ('low', 'Low Cost'),
        ('average', 'Average'),
        ('high', 'Premium')
    ], string='Price Level')
    
    # Material Lines
    material_line_ids = fields.One2many(
        'supplier.material.line',
        'supplier_id',
        string='Materials'
    )
    
    # Dates
    first_purchase_date = fields.Date(string='First Purchase')
    last_purchase_date = fields.Date(string='Last Purchase')
    days_since_last_purchase = fields.Integer(
        string='Days Since Last Purchase',
        compute='_compute_days_since',
        store=True
    )
    
    # Status
    is_active = fields.Boolean(string='Active', default=True)
    preferred_supplier = fields.Boolean(string='Preferred Supplier')
    
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string='Notes')

    @api.depends('total_purchase_value', 'total_invoices')
    def _compute_averages(self):
        for record in self:
            if record.total_invoices:
                record.avg_invoice_value = record.total_purchase_value / record.total_invoices
            else:
                record.avg_invoice_value = 0

    @api.depends('last_purchase_date')
    def _compute_days_since(self):
        today = fields.Date.today()
        for record in self:
            if record.last_purchase_date:
                record.days_since_last_purchase = (today - record.last_purchase_date).days
            else:
                record.days_since_last_purchase = 0

    @api.model
    def generate_supplier_analytics(self, date_from, date_to):
        """Generate analytics for all suppliers in date range"""
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError('No active ERPNext configuration found.')
        
        import requests
        
        # Fetch all purchase invoices in range
        url = f"{config.base_url}/api/resource/Purchase Invoice"
        filters = {
            'posting_date': ['between', [
                date_from.strftime('%Y-%m-%d'),
                date_to.strftime('%Y-%m-%d')
            ]],
            'docstatus': 1
        }
        params = {
            'filters': str(filters),
            'fields': '["name", "supplier", "grand_total", "posting_date"]'
        }
        
        try:
            response = requests.get(url, headers=config._get_headers(), params=params)
            response.raise_for_status()
            invoices = response.json().get('data', [])
            
            # Aggregate by supplier
            supplier_data = {}
            
            for inv in invoices:
                supplier = inv['supplier']
                if supplier not in supplier_data:
                    supplier_data[supplier] = {
                        'total_value': 0,
                        'invoice_count': 0,
                        'materials': set(),
                        'dates': []
                    }
                
                supplier_data[supplier]['total_value'] += inv['grand_total']
                supplier_data[supplier]['invoice_count'] += 1
                supplier_data[supplier]['dates'].append(inv['posting_date'])
            
            # Create/update supplier records
            for supplier_name, data in supplier_data.items():
                existing = self.search([
                    ('name', '=', supplier_name),
                    ('date_from', '=', date_from),
                    ('date_to', '=', date_to)
                ])
                
                vals = {
                    'name': supplier_name,
                    'date_from': date_from,
                    'date_to': date_to,
                    'total_purchase_value': data['total_value'],
                    'total_invoices': data['invoice_count'],
                    'first_purchase_date': min(data['dates']),
                    'last_purchase_date': max(data['dates']),
                }
                
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)
            
            return len(supplier_data)
            
        except Exception as e:
            _logger.error(f"Supplier analytics failed: {str(e)}")
            raise UserError(f'Failed to generate analytics: {str(e)}')

    def action_compare_suppliers(self):
        """Open comparison view for selected suppliers"""
        return {
            'name': 'Supplier Comparison',
            'type': 'ir.actions.act_window',
            'res_model': 'supplier.analytics',
            'view_mode': 'graph,pivot',
            'domain': [('id', 'in', self.ids)],
        }


class SupplierMaterialLine(models.Model):
    _name = 'supplier.material.line'
    _description = 'Supplier Material Line'
    _order = 'total_value desc'

    supplier_id = fields.Many2one(
        'supplier.analytics',
        string='Supplier',
        required=True,
        ondelete='cascade'
    )
    material_code = fields.Char(string='Material Code', required=True)
    material_name = fields.Char(string='Material Name')
    
    # Purchase Stats
    purchase_count = fields.Integer(string='Purchases')
    total_quantity = fields.Float(string='Total Qty')
    total_value = fields.Monetary(
        string='Total Value',
        currency_field='currency_id'
    )
    avg_unit_price = fields.Monetary(
        string='Avg Price',
        currency_field='currency_id'
    )
    last_purchase_date = fields.Date(string='Last Purchase')
    
    currency_id = fields.Many2one(
        'res.currency',
        related='supplier_id.currency_id',
        store=True
    )