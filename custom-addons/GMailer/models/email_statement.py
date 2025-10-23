from odoo import models, fields, api
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from email import message_from_bytes
import base64
from bs4 import BeautifulSoup
import re
from datetime import datetime

class EmailStatement(models.Model):
    _name = 'email.statement'
    _description = 'Email Bank Statement'
    _order = 'date desc'

    name = fields.Char(string='Subject', required=True)
    gmail_id = fields.Char(string='Gmail Message ID', required=True, index=True)
    date = fields.Datetime(string='Date', required=True)
    sender = fields.Char(string='From')
    body_html = fields.Html(string='Body HTML')
    body_text = fields.Text(string='Body Text')
    attachment_count = fields.Integer(string='Attachments', compute='_compute_attachment_count')
    transaction_ids = fields.One2many('bank.transaction', 'statement_id', string='Transactions')
    transaction_count = fields.Integer(string='Transactions', compute='_compute_transaction_count')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('parsed', 'Parsed'),
        ('imported', 'Imported'),
    ], default='draft', string='Status')
    
    @api.depends('transaction_ids')
    def _compute_transaction_count(self):
        for record in self:
            record.transaction_count = len(record.transaction_ids)
    
    def _compute_attachment_count(self):
        for record in self:
            record.attachment_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id)
            ])
    
    def action_parse_statement(self):
        """Parse the email content to extract transactions"""
        for record in self:
            transactions = self._extract_transactions(record.body_html or record.body_text)
            
            for trans in transactions:
                self.env['bank.transaction'].create({
                    'statement_id': record.id,
                    'date': trans.get('date'),
                    'description': trans.get('description'),
                    'amount': trans.get('amount'),
                    'transaction_type': trans.get('type'),
                    'reference': trans.get('reference'),
                })
            
            record.state = 'parsed'
    
    def _extract_transactions(self, content):
        """Extract transaction data from email content - customize based on your bank format"""
        transactions = []
        
        if not content:
            return transactions
        
        # Parse HTML content
        soup = BeautifulSoup(content, 'html.parser')
        text = soup.get_text()
        
        # Example pattern - adjust based on your bank's format
        # Pattern: Date | Description | Amount
        pattern = r'(\d{2}/\d{2}/\d{4})\s+([^\$]+)\s+\$?([\d,]+\.\d{2})'
        matches = re.findall(pattern, text)
        
        for match in matches:
            try:
                trans_date = datetime.strptime(match[0], '%m/%d/%Y')
                description = match[1].strip()
                amount = float(match[2].replace(',', ''))
                
                transactions.append({
                    'date': trans_date,
                    'description': description,
                    'amount': amount,
                    'type': 'debit' if amount < 0 else 'credit',
                    'reference': f"{trans_date.strftime('%Y%m%d')}-{description[:20]}"
                })
            except:
                continue
        
        return transactions
    
    @api.model
    def fetch_statements_from_gmail(self, credential_id=None):
        """Fetch bank statements from Gmail"""
        
        if not credential_id:
            credentials = self.env['google.credentials'].search([
                ('is_authenticated', '=', True)
            ], limit=1)
        else:
            credentials = self.env['google.credentials'].browse(credential_id)
        
        if not credentials:
            raise UserError('No authenticated Google credentials found')
        
        # Build Gmail service
        creds = Credentials(
            token=credentials.access_token,
            refresh_token=credentials.refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
        )
        
        service = build('gmail', 'v1', credentials=creds)
        
        # Search for bank statement emails - customize query
        query = 'subject:(statement OR "bank statement" OR transaction) from:(@yourbank.com)'
        results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
        messages = results.get('messages', [])
        
        imported_count = 0
        
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
            
            # Check if already imported
            if self.search([('gmail_id', '=', msg['id'])]):
                continue
            
            # Extract message details
            headers = msg_data['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            # Parse date
            from email.utils import parsedate_to_datetime
            msg_date = parsedate_to_datetime(date_str)
            
            # Extract body
            body_html = ''
            body_text = ''
            
            if 'parts' in msg_data['payload']:
                for part in msg_data['payload']['parts']:
                    if part['mimeType'] == 'text/html':
                        body_html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    elif part['mimeType'] == 'text/plain':
                        body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif 'body' in msg_data['payload'] and msg_data['payload']['body'].get('data'):
                body_text = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8')
            
            # Create statement record
            statement = self.create({
                'name': subject,
                'gmail_id': msg['id'],
                'date': msg_date,
                'sender': sender,
                'body_html': body_html,
                'body_text': body_text,
            })
            
            # Auto-parse if configured
            statement.action_parse_statement()
            imported_count += 1
        
        return imported_count