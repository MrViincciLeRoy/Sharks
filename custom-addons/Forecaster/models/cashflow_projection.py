from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class CashflowProjection(models.Model):
    _name = 'cashflow.projection'
    _description = 'Cashflow Projection'
    _order = 'projection_date'

    name = fields.Char(string='Projection Name', compute='_compute_name', store=True)
    projection_date = fields.Date(string='Projection Date', required=True)
    
    # Opening Balance
    opening_balance = fields.Monetary(string='Opening Balance', currency_field='currency_id')
    
    # Expected Inflows
    expected_income = fields.Monetary(string='Expected Income', currency_field='currency_id')
    confirmed_income = fields.Monetary(string='Confirmed Income', currency_field='currency_id')
    
    # Expected Outflows
    expected_expenses = fields.Monetary(string='Expected Expenses', currency_field='currency_id')
    confirmed_expenses = fields.Monetary(string='Confirmed Expenses', currency_field='currency_id')
    
    # Closing Balance
    projected_balance = fields.Monetary(
        string='Projected Balance',
        compute='_compute_projected_balance',
        store=True,
        currency_field='currency_id'
    )
    minimum_balance = fields.Monetary(
        string='Minimum Required',
        default=10000,
        currency_field='currency_id'
    )
    balance_status = fields.Selection([
        ('healthy', 'Healthy'),
        ('warning', 'Warning'),
        ('critical', 'Critical')
    ], string='Status', compute='_compute_balance_status', store=True)
    
    # Confidence
    confidence_level = fields.Float(string='Confidence %', digits=(5, 2))
    
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string='Notes')
    
    # Related forecasts
    forecast_ids = fields.Many2many(
        'expense.forecast',
        string='Related Forecasts',
        compute='_compute_forecast_ids'
    )

    @api.depends('projection_date')
    def _compute_name(self):
        for record in self:
            record.name = f"Cashflow Projection - {record.projection_date}"

    @api.depends('opening_balance', 'expected_income', 'expected_expenses')
    def _compute_projected_balance(self):
        for record in self:
            record.projected_balance = (
                record.opening_balance +
                record.expected_income -
                record.expected_expenses
            )

    @api.depends('projected_balance', 'minimum_balance')
    def _compute_balance_status(self):
        for record in self:
            if record.projected_balance >= record.minimum_balance * 1.5:
                record.balance_status = 'healthy'
            elif record.projected_balance >= record.minimum_balance:
                record.balance_status = 'warning'
            else:
                record.balance_status = 'critical'

    @api.depends('projection_date')
    def _compute_forecast_ids(self):
        for record in self:
            forecasts = self.env['expense.forecast'].search([
                ('forecast_date', '=', record.projection_date)
            ])
            record.forecast_ids = [(6, 0, forecasts.ids)]

    def action_generate_projection(self):
        """Generate cashflow projection based on forecasts"""
        self.ensure_one()
        
        # Get current bank balance (you'll need to implement this based on your bank integration)
        current_balance = self._get_current_bank_balance()
        
        # Get forecasts for this date
        forecasts = self.env['expense.forecast'].search([
            ('forecast_date', '=', self.projection_date)
        ])
        
        expected_income = sum(
            f.predicted_amount for f in forecasts if f.forecast_type == 'income'
        )
        expected_expenses = sum(
            f.predicted_amount for f in forecasts if f.forecast_type == 'expense'
        )
        
        # Calculate confidence based on forecast confidence scores
        if forecasts:
            avg_confidence = sum(f.confidence_score for f in forecasts) / len(forecasts)
        else:
            avg_confidence = 50
        
        self.write({
            'opening_balance': current_balance,
            'expected_income': expected_income,
            'expected_expenses': expected_expenses,
            'confidence_level': avg_confidence,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Projection Generated',
                'message': f'Projected balance: {self.projected_balance:.2f}',
                'type': 'success',
            }
        }

    def _get_current_bank_balance(self):
        """Get current bank balance - implement based on your needs"""
        # This is a placeholder - implement actual logic based on your system
        # Could query bank API, last transaction, or manual entry
        return 50000.0

    @api.model
    def generate_projections(self, months=6):
        """Generate projections for next N months"""
        today = datetime.now().date()
        
        created_count = 0
        for month_offset in range(1, months + 1):
            projection_date = today + relativedelta(months=month_offset)
            
            # Check if projection exists
            existing = self.search([
                ('projection_date', '=', projection_date)
            ])
            
            if not existing:
                projection = self.create({
                    'projection_date': projection_date,
                })
                projection.action_generate_projection()
                created_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Projections Created',
                'message': f'Created {created_count} cashflow projections',
                'type': 'success',
            }
        }