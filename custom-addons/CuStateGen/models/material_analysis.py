from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class MaterialAnalysis(models.Model):
    _name = 'material.analysis'
    _description = 'Material Purchase Analysis'
    _order = 'analysis_date desc'

    name = fields.Char(string='Analysis Name', required=True)
    analysis_date = fields.Date(string='Analysis Date', default=fields.Date.today)
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True, default=fields.Date.today)
    
    # Analysis Results
    material_line_ids = fields.One2many(
        'material.analysis.line',
        'analysis_id',
        string='Material Lines'
    )
    line_count = fields.Integer(
        string='Materials Analyzed',
        compute='_compute_line_count'
    )
    
    # Summary Statistics
    total_materials = fields.Integer(
        string='Total Materials',
        compute='_compute_statistics',
        store=True
    )
    total_purchase_value = fields.Monetary(
        string='Total Purchase Value',
        currency_field='currency_id',
        compute='_compute_statistics',
        store=True
    )
    repeated_materials = fields.Integer(
        string='Repeated Purchases',
        compute='_compute_statistics',
        store=True,
        help='Materials purchased more than once'
    )
    unique_suppliers = fields.Integer(
        string='Unique Suppliers',
        compute='_compute_statistics',
        store=True
    )
    
    # Top Items
    top_material = fields.Char(
        string='Top Material',
        compute='_compute_top_items',
        store=True
    )
    top_material_value = fields.Monetary(
        string='Top Material Value',
        currency_field='currency_id',
        compute='_compute_top_items',
        store=True
    )
    top_supplier = fields.Char(
        string='Top Supplier',
        compute='_compute_top_items',
        store=True
    )
    top_supplier_value = fields.Monetary(
        string='Top Supplier Value',
        currency_field='currency_id',
        compute='_compute_top_items',
        store=True
    )
    
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('analyzed', 'Analyzed')
    ], default='draft', string='Status')
    notes = fields.Text(string='Notes')

    @api.depends('material_line_ids')
    def _compute_line_count(self):
        for record in self:
            record.line_count = len(record.material_line_ids)

    @api.depends('material_line_ids.total_value', 'material_line_ids.purchase_count')
    def _compute_statistics(self):
        for record in self:
            lines = record.material_line_ids
            record.total_materials = len(lines)
            record.total_purchase_value = sum(lines.mapped('total_value'))
            record.repeated_materials = len(lines.filtered(lambda l: l.purchase_count > 1))
            record.unique_suppliers = len(set(lines.mapped('primary_supplier')))

    @api.depends('material_line_ids.total_value')
    def _compute_top_items(self):
        for record in self:
            if not record.material_line_ids:
                record.top_material = False
                record.top_material_value = 0
                record.top_supplier = False
                record.top_supplier_value = 0
                continue
            
            # Top material by value
            top_mat = max(record.material_line_ids, key=lambda l: l.total_value, default=False)
            if top_mat:
                record.top_material = top_mat.material_name
                record.top_material_value = top_mat.total_value
            
            # Top supplier by value
            supplier_totals = {}
            for line in record.material_line_ids:
                if line.primary_supplier:
                    supplier_totals[line.primary_supplier] = supplier_totals.get(
                        line.primary_supplier, 0
                    ) + line.total_value
            
            if supplier_totals:
                top_supp = max(supplier_totals, key=supplier_totals.get)
                record.top_supplier = top_supp
                record.top_supplier_value = supplier_totals[top_supp]

    def action_analyze_materials(self):
        """Fetch and analyze material purchases from ERPNext"""
        self.ensure_one()
        
        config = self.env['erpnext.config'].search([('active', '=', True)], limit=1)
        if not config:
            raise UserError('No active ERPNext configuration found.')
        
        # Clear existing lines
        self.material_line_ids.unlink()
        
        # Fetch purchase orders and invoices
        self._analyze_purchase_orders(config)
        
        # Calculate trends and patterns
        self._detect_patterns()
        
        self.state = 'analyzed'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Analysis Complete',
                'message': f'Analyzed {self.line_count} materials from {self.unique_suppliers} suppliers',
                'type': 'success',
            }
        }

    def _analyze_purchase_orders(self, config):
        """Fetch purchase orders from ERPNext and aggregate by material"""
        import requests
        
        # Fetch Purchase Invoices
        url = f"{config.base_url}/api/resource/Purchase Invoice"
        filters = {
            'posting_date': ['between', [
                self.date_from.strftime('%Y-%m-%d'),
                self.date_to.strftime('%Y-%m-%d')
            ]],
            'docstatus': 1
        }
        params = {
            'filters': str(filters),
            'fields': '["name", "supplier", "posting_date", "grand_total"]'
        }
        
        try:
            response = requests.get(url, headers=config._get_headers(), params=params)
            response.raise_for_status()
            invoices = response.json().get('data', [])
            
            _logger.info(f"Found {len(invoices)} purchase invoices")
            
            # For each invoice, fetch items
            material_data = {}  # {material_code: {data}}
            
            for invoice in invoices:
                self._fetch_invoice_items(config, invoice, material_data)
            
            # Create analysis lines
            for material_code, data in material_data.items():
                self.env['material.analysis.line'].create({
                    'analysis_id': self.id,
                    'material_code': material_code,
                    'material_name': data['name'],
                    'purchase_count': data['count'],
                    'total_quantity': data['qty'],
                    'total_value': data['value'],
                    'avg_unit_price': data['value'] / data['qty'] if data['qty'] else 0,
                    'primary_supplier': data['main_supplier'],
                    'supplier_count': len(data['suppliers']),
                    'last_purchase_date': data['last_date'],
                    'price_trend': data.get('trend', 'stable'),
                })
            
        except Exception as e:
            _logger.error(f"Analysis failed: {str(e)}")
            raise UserError(f'Analysis failed: {str(e)}')

    def _fetch_invoice_items(self, config, invoice, material_data):
        """Fetch items from a purchase invoice"""
        import requests
        
        url = f"{config.base_url}/api/resource/Purchase Invoice/{invoice['name']}"
        
        try:
            response = requests.get(url, headers=config._get_headers())
            response.raise_for_status()
            invoice_data = response.json().get('data', {})
            
            items = invoice_data.get('items', [])
            supplier = invoice_data.get('supplier')
            posting_date = invoice_data.get('posting_date')
            
            for item in items:
                material_code = item.get('item_code')
                if not material_code:
                    continue
                
                if material_code not in material_data:
                    material_data[material_code] = {
                        'name': item.get('item_name', material_code),
                        'count': 0,
                        'qty': 0,
                        'value': 0,
                        'suppliers': set(),
                        'main_supplier': supplier,
                        'last_date': posting_date,
                        'prices': []
                    }
                
                data = material_data[material_code]
                data['count'] += 1
                data['qty'] += item.get('qty', 0)
                data['value'] += item.get('amount', 0)
                data['suppliers'].add(supplier)
                data['prices'].append(item.get('rate', 0))
                
                # Update last date
                if posting_date > data['last_date']:
                    data['last_date'] = posting_date
                
        except Exception as e:
            _logger.warning(f"Failed to fetch items for {invoice['name']}: {str(e)}")

    def _detect_patterns(self):
        """Detect purchasing patterns and trends"""
        for line in self.material_line_ids:
            # Calculate price trend
            if len(line.analysis_id.material_line_ids) > 1:
                # Simple trend: compare to average
                avg_price = sum(
                    l.avg_unit_price for l in line.analysis_id.material_line_ids
                ) / len(line.analysis_id.material_line_ids)
                
                if line.avg_unit_price > avg_price * 1.1:
                    line.price_trend = 'increasing'
                elif line.avg_unit_price < avg_price * 0.9:
                    line.price_trend = 'decreasing'
                else:
                    line.price_trend = 'stable'
            
            # Mark repeated purchases
            if line.purchase_count > 3:
                line.is_repeated = True

    def action_view_supplier_analytics(self):
        """View supplier-specific analytics"""
        self.ensure_one()
        
        return {
            'name': 'Supplier Analytics',
            'type': 'ir.actions.act_window',
            'res_model': 'supplier.analytics',
            'view_mode': 'tree,form',
            'context': {
                'default_analysis_id': self.id,
            }
        }


class MaterialAnalysisLine(models.Model):
    _name = 'material.analysis.line'
    _description = 'Material Analysis Line'
    _order = 'total_value desc'

    analysis_id = fields.Many2one(
        'material.analysis',
        string='Analysis',
        required=True,
        ondelete='cascade'
    )
    
    # Material Info
    material_code = fields.Char(string='Material Code', required=True)
    material_name = fields.Char(string='Material Name', required=True)
    material_group = fields.Char(string='Group')
    
    # Purchase Stats
    purchase_count = fields.Integer(string='Purchase Count')
    total_quantity = fields.Float(string='Total Quantity')
    total_value = fields.Monetary(
        string='Total Value',
        currency_field='currency_id'
    )
    avg_unit_price = fields.Monetary(
        string='Avg Unit Price',
        currency_field='currency_id'
    )
    
    # Supplier Info
    primary_supplier = fields.Char(string='Primary Supplier')
    supplier_count = fields.Integer(string='Suppliers Used')
    
    # Dates
    first_purchase_date = fields.Date(string='First Purchase')
    last_purchase_date = fields.Date(string='Last Purchase')
    
    # Patterns
    is_repeated = fields.Boolean(string='Repeated Purchase', default=False)
    purchase_frequency = fields.Selection([
        ('one_time', 'One-time'),
        ('occasional', 'Occasional'),
        ('regular', 'Regular'),
        ('frequent', 'Frequent')
    ], string='Frequency', compute='_compute_frequency')
    price_trend = fields.Selection([
        ('increasing', 'Increasing'),
        ('stable', 'Stable'),
        ('decreasing', 'Decreasing')
    ], string='Price Trend', default='stable')
    
    # Inventory Link
    has_inventory_link = fields.Boolean(
        string='In Inventory',
        help='Material exists in ERPNext inventory'
    )
    current_stock = fields.Float(string='Current Stock')
    
    currency_id = fields.Many2one(
        'res.currency',
        related='analysis_id.currency_id',
        store=True
    )

    @api.depends('purchase_count', 'first_purchase_date', 'last_purchase_date')
    def _compute_frequency(self):
        for record in self:
            if record.purchase_count == 1:
                record.purchase_frequency = 'one_time'
            elif record.purchase_count <= 3:
                record.purchase_frequency = 'occasional'
            elif record.purchase_count <= 6:
                record.purchase_frequency = 'regular'
            else:
                record.purchase_frequency = 'frequent'

    def action_view_purchase_history(self):
        """View detailed purchase history for this material"""
        self.ensure_one()
        
        # This would link to ERPNext purchase history
        return {
            'type': 'ir.actions.act_url',
            'url': f"{self.env['erpnext.config'].search([], limit=1).base_url}/app/item/{self.material_code}",
            'target': 'new',
        }