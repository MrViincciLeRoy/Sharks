from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class BankTransactionInsights(models.Model):
    _inherit = 'bank.transaction'

    # Insight Fields
    is_recurring = fields.Boolean(string='Recurring Transaction', compute='_compute_insights', store=True)
    is_unusual = fields.Boolean(string='Unusual Amount', compute='_compute_insights', store=True)
    spending_pattern = fields.Selection([
        ('regular', 'Regular'),
        ('occasional', 'Occasional'),
        ('one_time', 'One-time')
    ], string='Pattern', compute='_compute_insights', store=True)
    similar_transaction_count = fields.Integer(string='Similar Transactions', compute='_compute_similar_count')
    forecast_variance = fields.Monetary(
        string='vs Forecast',
        currency_field='currency_id',
        help='Difference from forecasted amount'
    )
    risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk')
    ], string='Risk Level', compute='_compute_risk_level', store=True)

    @api.depends('description', 'amount', 'date')
    def _compute_insights(self):
        for record in self:
            # Check if recurring
            similar_trans = self._find_similar_transactions(record)
            record.is_recurring = len(similar_trans) >= 3
            
            # Check if unusual
            if record.category_id:
                category_trans = self.search([
                    ('category_id', '=', record.category_id.id),
                    ('id', '!=', record.id)
                ])
                if category_trans:
                    amounts = [abs(t.amount) for t in category_trans]
                    avg = sum(amounts) / len(amounts)
                    std_dev = (sum((x - avg) ** 2 for x in amounts) / len(amounts)) ** 0.5
                    record.is_unusual = abs(record.amount) > (avg + 2 * std_dev)
                else:
                    record.is_unusual = False
            else:
                record.is_unusual = False
            
            # Determine spending pattern
            if len(similar_trans) >= 3:
                # Check frequency
                dates = sorted([t.date for t in similar_trans])
                if len(dates) >= 2:
                    intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                    avg_interval = sum(intervals) / len(intervals)
                    
                    if avg_interval <= 35:  # Monthly or more frequent
                        record.spending_pattern = 'regular'
                    elif avg_interval <= 95:  # Quarterly
                        record.spending_pattern = 'occasional'
                    else:
                        record.spending_pattern = 'one_time'
                else:
                    record.spending_pattern = 'occasional'
            else:
                record.spending_pattern = 'one_time'

    @api.depends('is_unusual', 'is_recurring', 'category_id')
    def _compute_risk_level(self):
        for record in self:
            if record.is_unusual and not record.category_id:
                record.risk_level = 'high'
            elif record.is_unusual or not record.category_id:
                record.risk_level = 'medium'
            else:
                record.risk_level = 'low'

    def _compute_similar_count(self):
        for record in self:
            similar = self._find_similar_transactions(record)
            record.similar_transaction_count = len(similar)

    def _find_similar_transactions(self, transaction):
        """Find transactions similar to this one"""
        if not transaction.description:
            return self.env['bank.transaction']
        
        # Split description into words
        words = transaction.description.lower().split()
        significant_words = [w for w in words if len(w) > 3][:3]  # Top 3 words
        
        if not significant_words:
            return self.env['bank.transaction']
        
        # Search for transactions with similar descriptions
        domain = [('id', '!=', transaction.id)]
        for word in significant_words:
            domain.append(('description', 'ilike', word))
        
        similar = self.search(domain, limit=20)
        
        # Filter by similar amount (within 10%)
        if transaction.amount != 0:
            similar = similar.filtered(
                lambda t: abs(abs(t.amount) - abs(transaction.amount)) / abs(transaction.amount) < 0.1
            )
        
        return similar

    def action_view_similar_transactions(self):
        """View similar transactions"""
        self.ensure_one()
        similar = self._find_similar_transactions(self)
        
        return {
            'name': 'Similar Transactions',
            'type': 'ir.actions.act_window',
            'res_model': 'bank.transaction',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', similar.ids)],
            'context': {'default_category_id': self.category_id.id if self.category_id else False}
        }

    @api.model
    def get_spending_insights(self, period='month'):
        """Get spending insights for a period"""
        if period == 'month':
            date_from = datetime.now().date().replace(day=1)
            date_to = date_from + relativedelta(months=1) - relativedelta(days=1)
        elif period == 'quarter':
            date_from = datetime.now().date().replace(day=1, month=((datetime.now().month-1)//3)*3+1)
            date_to = date_from + relativedelta(months=3) - relativedelta(days=1)
        else:  # year
            date_from = datetime.now().date().replace(day=1, month=1)
            date_to = date_from + relativedelta(years=1) - relativedelta(days=1)
        
        transactions = self.search([
            ('date', '>=', date_from),
            ('date', '<=', date_to)
        ])
        
        insights = {
            'total_transactions': len(transactions),
            'total_spent': sum(abs(t.amount) for t in transactions if t.transaction_type == 'debit'),
            'total_received': sum(abs(t.amount) for t in transactions if t.transaction_type == 'credit'),
            'recurring_count': len(transactions.filtered(lambda t: t.is_recurring)),
            'unusual_count': len(transactions.filtered(lambda t: t.is_unusual)),
            'high_risk_count': len(transactions.filtered(lambda t: t.risk_level == 'high')),
            'uncategorized_count': len(transactions.filtered(lambda t: not t.category_id)),
            'top_categories': {},
            'largest_transaction': None,
            'most_frequent_merchant': None,
        }
        
        # Top categories
        for trans in transactions.filtered(lambda t: t.category_id):
            cat_name = trans.category_id.name
            if cat_name not in insights['top_categories']:
                insights['top_categories'][cat_name] = 0
            insights['top_categories'][cat_name] += abs(trans.amount)
        
        # Largest transaction
        if transactions:
            largest = max(transactions, key=lambda t: abs(t.amount))
            insights['largest_transaction'] = {
                'description': largest.description,
                'amount': abs(largest.amount),
                'date': largest.date
            }
        
        return insights


class TransactionInsightWizard(models.TransientModel):
    _name = 'transaction.insight.wizard'
    _description = 'Transaction Insights Wizard'

    period = fields.Selection([
        ('week', 'Last Week'),
        ('month', 'Last Month'),
        ('quarter', 'Last Quarter'),
        ('year', 'Last Year')
    ], string='Period', default='month', required=True)
    
    include_forecast = fields.Boolean(string='Include Forecast Comparison', default=True)
    include_trends = fields.Boolean(string='Include Trend Analysis', default=True)
    include_anomalies = fields.Boolean(string='Highlight Anomalies', default=True)

    def action_generate_insights(self):
        """Generate comprehensive insights report"""
        self.ensure_one()
        
        # Calculate date range
        today = datetime.now().date()
        if self.period == 'week':
            date_from = today - relativedelta(weeks=1)
        elif self.period == 'month':
            date_from = today - relativedelta(months=1)
        elif self.period == 'quarter':
            date_from = today - relativedelta(months=3)
        else:  # year
            date_from = today - relativedelta(years=1)
        
        # Create analytics record
        analytics = self.env['expense.analytics'].create({
            'name': f'Insights Report - {self.period.title()}',
            'date_from': date_from,
            'date_to': today,
        })
        analytics.action_refresh_analysis()
        
        return {
            'name': 'Insights Report',
            'type': 'ir.actions.act_window',
            'res_model': 'expense.analytics',
            'res_id': analytics.id,
            'view_mode': 'form',
            'target': 'current',
        }