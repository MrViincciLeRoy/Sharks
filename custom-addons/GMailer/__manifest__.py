{
    'name': 'Email Statement Importer',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Import bank statements from Gmail using Google Auth',
    'description': """
        This module allows you to:
        - Authenticate with Google OAuth
        - Fetch bank statements from Gmail
        - Parse and store transactions
        - Automatic periodic imports
    """,
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'depends': ['base', 'account', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/google_credentials_views.xml',
        'views/email_statement_views.xml',
        'views/bank_transaction_views.xml',
        'data/cron_jobs.xml',
    ],
    'external_dependencies': {
        'python': ['google-auth', 'google-auth-oauthlib', 'google-api-python-client', 'beautifulsoup4'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}