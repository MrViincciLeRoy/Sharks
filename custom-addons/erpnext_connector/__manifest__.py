{
    'name': 'ERPNext Connector',
    'version': '1.0',
    'category': 'Integration',
    'summary': 'Bidirectional sync with ERPNext',
    'description': """
        Connect Odoo with ERPNext systems
        - Customer sync
        - Transaction sync
        - Invoice sync
        - Statement generation
    """,
    'depends': ['base', 'account', 'investec_banking'],
    'data': [
        'security/ir.model.access.csv',
        'views/erpnext_config_views.xml',
        'views/sync_log_views.xml',
    ],
    'installable': True,
    'application': True,
}