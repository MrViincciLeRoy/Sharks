from odoo import models, fields, api

class TransactionCategory(models.Model):
    _name = 'transaction.category'
    _description = 'Bank Transaction Category'
    _order = 'name'

    name = fields.Char(string='Category Name', required=True)
    erpnext_account = fields.Char(
        string='ERPNext Account', 
        required=True,
        help='The account code in ERPNext (e.g., "Expenses - Company")'
    )
    transaction_type = fields.Selection([
        ('expense', 'Expense'),
        ('income', 'Income'),
        ('transfer', 'Transfer'),
    ], string='Type', required=True, default='expense')
    keywords = fields.Text(
        string='Auto-match Keywords',
        help='Comma-separated keywords for auto-categorization'
    )
    active = fields.Boolean(default=True)
    color = fields.Integer(string='Color Index')

    @api.model
    def auto_categorize_transaction(self, description):
        """Find matching category based on keywords"""
        if not description:
            return False
        
        description_lower = description.lower()
        categories = self.search([('active', '=', True)])
        
        for category in categories:
            if category.keywords:
                keywords = [k.strip().lower() for k in category.keywords.split(',')]
                if any(keyword in description_lower for keyword in keywords):
                    return category
        
        return False
