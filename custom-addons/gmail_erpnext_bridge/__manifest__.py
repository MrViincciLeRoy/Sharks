{
    'name': 'GMailer-ERPNext Bridge',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Connect GMailer bank statements with ERPNext',
    'description': """
        Bridge module that connects GMailer and ERPNext Connector:
        - Extends bank transactions with ERPNext sync fields
        - Adds transaction categorization
        - Enables one-click sync to ERPNext
        - Bulk sync capabilities
    """,
    'author': 'Your Company',
    'depends': ['GMailer', 'erpnext_connector'],
    'data': [
        'security/ir.model.access.csv',
        'views/transaction_category_views.xml',
        'views/bank_transaction_extended_views.xml',
        'data/default_categories.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
