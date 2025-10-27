{
    'name': 'Forecaster',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Advanced expense forecasting and analytics for businesses',
    'description': """
        Comprehensive expense forecasting and analytics module:
        
        Features:
        - Automatic expense forecasting using multiple algorithms
        - Historical trend analysis
        - Seasonal adjustment patterns
        - Recurring transaction detection
        - Cashflow projections
        - Spending insights and anomaly detection
        - Category-based analysis
        - Support for categorized and uncategorized transactions
        - Risk assessment
        - Variance tracking
        
        Perfect for:
        - Business owners tracking expenses
        - Accountants managing cashflow
        - Financial planning and budgeting
        - Identifying spending patterns
        - Detecting unusual transactions
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': ['base', 'account', 'gmail_erpnext_bridge'],
    'data': [
        'security/ir.model.access.csv',
        'views/expense_forecast_views.xml',
        'views/expense_analytics_views.xml',
        'views/cashflow_projection_views.xml',
        'views/bank_transaction_insights_views.xml',
        'views/dashboard_views.xml',
        'data/cron_jobs.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}