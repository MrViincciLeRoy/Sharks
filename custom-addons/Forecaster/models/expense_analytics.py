from odoo import models, fields, api
from datetime import datetime
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)

class ExpenseAnalytics(models.Model):
    _name = 'expense.analytics'
    _description = 'Expense Analytics Dashboard'
    _order = 'create_date desc'

    name = fields.Char(string='Analysis Name', required=True)
    date_from = fields.Date(string='From Date', required=True)
    date_to = fields.Date(string='To Date', required=True)
    
    # Summary Fields
    total_expenses = fields.Monetary(string='Total Expenses', currency_field='currency_id')
    total_income = fields.Monetary(string='Total Income', currency_field='currency_id')
    net_cashflow = fields.Monetary(string='Net Cashflow', currency_field='currency_id')
    avg_daily_expense = fields.Monetary(string='Avg Daily Expense', currency_field='currency_id')
    avg_transaction_size = fields.Monetary(string='Avg Transaction Size', currency_field='currency_id')
    
    # Transaction Counts
    total_transactions = fields.Integer(string='Total Transactions')
    categorized_count = fields.Integer(string='Categorized')
    uncategorized_count = fields.Integer(string='Uncategorized')
    categorization_rate = fields.Float(string='Categorization %', digits=(5, 2))
    
    # Category Analysis
    top_expense_category = fields.Char(string='Top Expense Category')
    top_expense_amount = fields.Monetary(string='Top Expense Amount', currency_field='currency_id')
    
    # Trends
    expense_trend = fields.Selection([
        ('increasing', 'Increasing'),
        ('stable', 'Stable'),
        ('decreasing', 'Decreasing')
    ], string='Expense Trend')
    trend_percentage = fields.Float(string='Trend %', digits=(5, 2))
    
    # Anomalies
    unusual_transactions = fields.Integer(string='Unusual Transactions')
    
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    notes = fields.Text(string='Analysis Notes')

    def action_refresh_analysis(self):
        """Recalculate all analytics"""
        self.ensure_one()
        
        # Get transactions in date range
        transactions = self.env['bank.transaction'].search([
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to)
        ])
        
        if not transactions:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Data',
                    'message': 'No transactions found in the selected period',
                    'type': 'warning',
                }
            }
        
        # Calculate summary metrics
        expenses = [t for t in transactions if t.transaction_type == 'debit']
        income = [t for t in transactions if t.transaction_type == 'credit']
        
        total_expenses = sum(abs(t.amount) for t in expenses)
        total_income = sum(abs(t.amount) for t in income)
        
        days = (self.date_to - self.date_from).days + 1
        avg_daily_expense = total_expenses / days if days > 0 else 0
        
        # Transaction counts
        categorized = [t for t in transactions if t.category_id]
        uncategorized = [t for t in transactions if not t.category_id]
        
        categorization_rate = (len(categorized) / len(transactions) * 100) if transactions else 0
        
        # Category analysis
        category_totals = {}
        for trans in expenses:
            if trans.category_id:
                cat_name = trans.category_id.name
                if cat_name not in category_totals:
                    category_totals[cat_name] = 0
                category_totals[cat_name] += abs(trans.amount)
        
        top_category = None
        top_amount = 0
        if category_totals:
            top_category = max(category_totals, key=category_totals.get)
            top_amount = category_totals[top_category]
        
        # Trend analysis
        trend, trend_pct = self._calculate_trend(transactions, self.date_from, self.date_to)
        
        # Detect unusual transactions
        unusual_count = self._detect_unusual_transactions(transactions)
        
        # Update record
        self.write({
            'total_expenses': total_expenses,
            'total_income': total_income,
            'net_cashflow': total_income - total_expenses,
            'avg_daily_expense': avg_daily_expense,
            'avg_transaction_size': sum(abs(t.amount) for t in transactions) / len(transactions),
            'total_transactions': len(transactions),
            'categorized_count': len(categorized),
            'uncategorized_count': len(uncategorized),
            'categorization_rate': categorization_rate,
            'top_expense_category': top_category,
            'top_expense_amount': top_amount,
            'expense_trend': trend,
            'trend_percentage': trend_pct,
            'unusual_transactions': unusual_count,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Analysis Updated',
                'message': f'Analyzed {len(transactions)} transactions',
                'type': 'success',
            }
        }

    def _calculate_trend(self, transactions, date_from, date_to):
        """Calculate expense trend over period"""
        if not transactions:
            return 'stable', 0
        
        expenses = [t for t in transactions if t.transaction_type == 'debit']
        if len(expenses) < 4:
            return 'stable', 0
        
        # Split period in half
        mid_date = date_from + (date_to - date_from) / 2
        
        first_half = [t for t in expenses if t.date < mid_date]
        second_half = [t for t in expenses if t.date >= mid_date]
        
        if not first_half or not second_half:
            return 'stable', 0
        
        first_avg = sum(abs(t.amount) for t in first_half) / len(first_half)
        second_avg = sum(abs(t.amount) for t in second_half) / len(second_half)
        
        if first_avg == 0:
            return 'stable', 0
        
        change_pct = ((second_avg - first_avg) / first_avg) * 100
        
        if change_pct > 10:
            return 'increasing', change_pct
        elif change_pct < -10:
            return 'decreasing', change_pct
        else:
            return 'stable', change_pct

    def _detect_unusual_transactions(self, transactions):
        """Detect transactions that are statistical outliers"""
        if len(transactions) < 10:
            return 0
        
        amounts = [abs(t.amount) for t in transactions]
        avg = sum(amounts) / len(amounts)
        
        # Calculate standard deviation
        variance = sum((x - avg) ** 2 for x in amounts) / len(amounts)
        std_dev = variance ** 0.5
        
        # Count transactions more than 2 standard deviations from mean
        threshold = avg + (2 * std_dev)
        unusual_count = len([a for a in amounts if a > threshold])
        
        return unusual_count

    @api.model
    def create_monthly_analysis(self, year=None, month=None):
        """Create analysis for a specific month"""
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month
        
        date_from = datetime(year, month, 1).date()
        date_to = (date_from + relativedelta(months=1) - relativedelta(days=1))
        
        analysis = self.create({
            'name': f'{date_from.strftime("%B %Y")} Analysis',
            'date_from': date_from,
            'date_to': date_to,
        })
        
        analysis.action_refresh_analysis()
        return analysis