{
    'name': 'CuStateGen',
    'version': '1.0.0',
    'category': 'Accounting/Reports',
    'summary': 'Generate customer statements and material analytics from ERPNext',
    'description': """
        Professional Customer Statement & Business Intelligence Module
        
        Core Features:
        =============
        • Customer account statements with outstanding balances
        • Invoice and payment history reports
        • Credit note tracking and reconciliation
        • Aging analysis (30/60/90 days)
        
        Material Analytics:
        ==================
        • Supplier purchase analysis
        • Repeated material purchase detection
        • Price trend analysis over time
        • Inventory correlation from ERPNext
        • Top suppliers by volume/value
        
        Integration:
        ===========
        • Syncs customers from ERPNext
        • Fetches invoices, payments, and credit notes
        • Links with Forecaster for payment predictions
        • Optional bank transaction correlation
        
        Output Formats:
        ==============
        • Professional PDF statements
        • Excel exports for analytics
        • Customizable templates
        • Bulk generation wizards
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': [
        'base',
        'account',
        'erpnext_connector',
        'Forecaster',  # For payment predictions
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/default_templates.xml',
        'views/customer_account_views.xml',
        'views/customer_statement_views.xml',
        'views/material_analysis_views.xml',
        'views/supplier_analytics_views.xml',
        'views/dashboard_views.xml',
        'wizards/statement_generator_wizard_views.xml',
        'wizards/bulk_sync_wizard_views.xml',
        'reports/statement_report.xml',
        'reports/material_report.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}