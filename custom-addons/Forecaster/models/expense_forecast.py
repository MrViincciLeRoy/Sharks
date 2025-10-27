from odoo import models, fields, api
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class ExpenseForecast(models.Model):
    _name = 'expense.forecast'
    _description = 'Expense Forecast'
    _order = 'forecast_date desc'

    name = fields.Char(string='Forecast Name', compute='_compute_name', store=True)
    forecast_date = fields.Date(string='Forecast Date', required=True)
    forecast_type = fields.Selection([
        ('expense', 'Expense'),
        ('income', 'Income')
    ], string='Type', required=True)
    category_id = fields.Many2one('transaction.category', string='Category')
    predicted_amount = fields.Monetary(string='Predicted Amount', currency_field='currency_id')
    confidence_score = fields.Float(string='Confidence %', digits=(5, 2))
    method = fields.Selection([
        ('historical_average', 'Historical Average'),
        ('trend_analysis', 'Trend Analysis'),
        ('recurring_pattern', 'Recurring Pattern'),
        ('seasonal_adjustment', 'Seasonal Adjustment'),
        ('manual', 'Manual Entry')
    ], string='Forecast Method')
    notes = fields.Text(string='Notes')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    actual_amount = fields.Monetary(string='Actual Amount', currency_field='currency_id')
    variance = fields.Monetary(string='Variance', compute='_compute_variance', store=True)
    variance_percentage = fields.Float(string='Variance %', compute='_compute_variance', store=True)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('realized', 'Realized')
    ], string='Status', default='draft')

    @api.depends('forecast_date', 'category_id', 'forecast_type')
    def _compute_name(self):
        for record in self:
            category_name = record.category_id.name if record.category_id else 'General'
            record.name = f"{record.forecast_type.title()} - {category_name} - {record.forecast_date}"

    @api.depends('predicted_amount', 'actual_amount')
    def _compute_variance(self):
        for record in self:
            if record.actual_amount:
                record.variance = record.actual_amount - record.predicted_amount
                if record.predicted_amount:
                    record.variance_percentage = (record.variance / abs(record.predicted_amount)) * 100
                else:
                    record.variance_percentage = 0
            else:
                record.variance = 0
                record.variance_percentage = 0


class ExpenseForecaster(models.Model):
    _name = 'expense.forecaster'
    _description = 'Expense Forecasting Engine'

    name = fields.Char(string='Forecaster Name', default='Default Forecaster')
    forecast_period_months = fields.Integer(string='Forecast Period (Months)', default=3)
    historical_period_months = fields.Integer(string='Historical Period (Months)', default=6)
    min_transactions_required = fields.Integer(string='Min Transactions Required', default=3)
    last_run = fields.Datetime(string='Last Run', readonly=True)
    include_uncategorized = fields.Boolean(string='Include Uncategorized', default=True)
    auto_update = fields.Boolean(string='Auto-update Forecasts', default=True)

    def generate_forecasts(self):
        """Generate forecasts for all categories"""
        self.ensure_one()
        
        # Get all categories
        categories = self.env['transaction.category'].search([('active', '=', True)])
        forecast_count = 0
        
        # Generate forecasts for categorized transactions
        for category in categories:
            for month_offset in range(1, self.forecast_period_months + 1):
                forecast_date = datetime.now().date() + relativedelta(months=month_offset)
                
                existing = self.env['expense.forecast'].search([
                    ('forecast_date', '=', forecast_date),
                    ('category_id', '=', category.id)
                ])
                
                if not existing:
                    forecast = self._calculate_forecast(category, forecast_date)
                    if forecast:
                        self.env['expense.forecast'].create(forecast)
                        forecast_count += 1
        
        # Generate forecasts for uncategorized transactions if enabled
        if self.include_uncategorized:
            for month_offset in range(1, self.forecast_period_months + 1):
                forecast_date = datetime.now().date() + relativedelta(months=month_offset)
                
                existing = self.env['expense.forecast'].search([
                    ('forecast_date', '=', forecast_date),
                    ('category_id', '=', False)
                ])
                
                if not existing:
                    forecast = self._calculate_uncategorized_forecast(forecast_date)
                    if forecast:
                        self.env['expense.forecast'].create(forecast)
                        forecast_count += 1
        
        self.last_run = fields.Datetime.now()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Forecasts Generated',
                'message': f'Generated {forecast_count} forecasts',
                'type': 'success',
            }
        }

    def _calculate_forecast(self, category, forecast_date):
        """Calculate forecast for a specific category and date"""
        from_date = datetime.now().date() - relativedelta(months=self.historical_period_months)
        
        transactions = self.env['bank.transaction'].search([
            ('category_id', '=', category.id),
            ('date', '>=', from_date),
            ('date', '<', datetime.now().date())
        ])
        
        if len(transactions) < self.min_transactions_required:
            return None
        
        # Method 1: Simple historical average
        amounts = [abs(t.amount) for t in transactions]
        avg_amount = sum(amounts) / len(amounts)
        
        # Method 2: Detect recurring patterns
        recurring_amount = self._detect_recurring_pattern(transactions)
        
        # Method 3: Calculate trend
        trend_factor = self._calculate_trend(transactions)
        
        # Method 4: Seasonal adjustment
        seasonal_factor = self._calculate_seasonal_factor(transactions, forecast_date)
        
        # Choose best method and calculate prediction
        if recurring_amount and len([t for t in transactions if abs(abs(t.amount) - recurring_amount) / recurring_amount < 0.1]) >= 3:
            predicted_amount = recurring_amount * (1 + trend_factor) * seasonal_factor
            confidence = 85
            method = 'recurring_pattern'
        elif abs(trend_factor) > 0.05:
            predicted_amount = avg_amount * (1 + trend_factor) * seasonal_factor
            confidence = 75
            method = 'trend_analysis'
        elif abs(seasonal_factor - 1.0) > 0.1:
            predicted_amount = avg_amount * seasonal_factor
            confidence = 70
            method = 'seasonal_adjustment'
        else:
            predicted_amount = avg_amount
            confidence = 65
            method = 'historical_average'
        
        # Determine transaction type
        debit_count = len([t for t in transactions if t.transaction_type == 'debit'])
        forecast_type = 'expense' if debit_count > len(transactions) / 2 else 'income'
        
        return {
            'forecast_date': forecast_date,
            'forecast_type': forecast_type,
            'category_id': category.id,
            'predicted_amount': predicted_amount,
            'confidence_score': confidence,
            'method': method,
            'notes': f'Based on {len(transactions)} historical transactions over {self.historical_period_months} months'
        }

    def _calculate_uncategorized_forecast(self, forecast_date):
        """Calculate forecast for uncategorized transactions"""
        from_date = datetime.now().date() - relativedelta(months=self.historical_period_months)
        
        transactions = self.env['bank.transaction'].search([
            ('category_id', '=', False),
            ('date', '>=', from_date),
            ('date', '<', datetime.now().date())
        ])
        
        if len(transactions) < self.min_transactions_required:
            return None
        
        amounts = [abs(t.amount) for t in transactions]
        avg_amount = sum(amounts) / len(amounts)
        
        debit_count = len([t for t in transactions if t.transaction_type == 'debit'])
        forecast_type = 'expense' if debit_count > len(transactions) / 2 else 'income'
        
        return {
            'forecast_date': forecast_date,
            'forecast_type': forecast_type,
            'category_id': False,
            'predicted_amount': avg_amount,
            'confidence_score': 50,
            'method': 'historical_average',
            'notes': f'Uncategorized transactions: {len(transactions)} over {self.historical_period_months} months'
        }

    def _detect_recurring_pattern(self, transactions):
        """Detect if there's a recurring payment pattern"""
        if len(transactions) < 3:
            return None
        
        amount_groups = {}
        for trans in transactions:
            amount = abs(trans.amount)
            found_group = False
            
            for key in amount_groups.keys():
                if abs(amount - key) / key < 0.05:
                    amount_groups[key].append(trans)
                    found_group = True
                    break
            
            if not found_group:
                amount_groups[amount] = [trans]
        
        max_count = 0
        recurring_amount = None
        
        for amount, group in amount_groups.items():
            if len(group) > max_count:
                max_count = len(group)
                recurring_amount = amount
        
        return recurring_amount if max_count >= 3 else None

    def _calculate_trend(self, transactions):
        """Calculate trend factor (-1 to 1)"""
        if len(transactions) < 4:
            return 0
        
        sorted_trans = sorted(transactions, key=lambda t: t.date)
        mid_point = len(sorted_trans) // 2
        first_half = sorted_trans[:mid_point]
        second_half = sorted_trans[mid_point:]
        
        first_avg = sum(abs(t.amount) for t in first_half) / len(first_half)
        second_avg = sum(abs(t.amount) for t in second_half) / len(second_half)
        
        if first_avg == 0:
            return 0
        
        trend = (second_avg - first_avg) / first_avg
        return max(-0.3, min(0.3, trend))

    def _calculate_seasonal_factor(self, transactions, forecast_date):
        """Calculate seasonal adjustment factor"""
        if len(transactions) < 12:
            return 1.0
        
        forecast_month = forecast_date.month
        
        # Group transactions by month
        monthly_amounts = {}
        for trans in transactions:
            month = trans.date.month
            if month not in monthly_amounts:
                monthly_amounts[month] = []
            monthly_amounts[month].append(abs(trans.amount))
        
        if forecast_month not in monthly_amounts:
            return 1.0
        
        # Calculate average for forecast month
        forecast_month_avg = sum(monthly_amounts[forecast_month]) / len(monthly_amounts[forecast_month])
        
        # Calculate overall average
        all_amounts = [amt for amounts in monthly_amounts.values() for amt in amounts]
        overall_avg = sum(all_amounts) / len(all_amounts)
        
        if overall_avg == 0:
            return 1.0
        
        return forecast_month_avg / overall_avg

    def get_forecast_summary(self, months=3):
        """Get forecast summary for dashboard"""
        self.ensure_one()
        
        from_date = datetime.now().date()
        to_date = from_date + relativedelta(months=months)
        
        forecasts = self.env['expense.forecast'].search([
            ('forecast_date', '>=', from_date),
            ('forecast_date', '<=', to_date)
        ])
        
        summary = {
            'total_expenses': sum(
                f.predicted_amount for f in forecasts if f.forecast_type == 'expense'
            ),
            'total_income': sum(
                f.predicted_amount for f in forecasts if f.forecast_type == 'income'
            ),
            'net_forecast': 0,
            'by_category': {},
            'by_month': {}
        }
        
        summary['net_forecast'] = summary['total_income'] - summary['total_expenses']
        
        # Group by category
        for forecast in forecasts:
            cat_name = forecast.category_id.name if forecast.category_id else 'Uncategorized'
            if cat_name not in summary['by_category']:
                summary['by_category'][cat_name] = {
                    'expenses': 0,
                    'income': 0
                }
            
            if forecast.forecast_type == 'expense':
                summary['by_category'][cat_name]['expenses'] += forecast.predicted_amount
            else:
                summary['by_category'][cat_name]['income'] += forecast.predicted_amount
        
        # Group by month
        for forecast in forecasts:
            month_key = forecast.forecast_date.strftime('%Y-%m')
            if month_key not in summary['by_month']:
                summary['by_month'][month_key] = {
                    'expenses': 0,
                    'income': 0,
                    'net': 0
                }
            
            if forecast.forecast_type == 'expense':
                summary['by_month'][month_key]['expenses'] += forecast.predicted_amount
            else:
                summary['by_month'][month_key]['income'] += forecast.predicted_amount
            
            summary['by_month'][month_key]['net'] = (
                summary['by_month'][month_key]['income'] - 
                summary['by_month'][month_key]['expenses']
            )
        
        return summary