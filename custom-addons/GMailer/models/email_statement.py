from odoo import models, fields, api
from odoo.exceptions import UserError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import base64
from bs4 import BeautifulSoup
import re
from datetime import datetime
import logging
import io
import pytz

_logger = logging.getLogger(__name__)

class EmailStatement(models.Model):
    _name = 'email.statement'
    _description = 'Email Bank Statement'
    _order = 'date desc'

    name = fields.Char(string='Subject', required=True)
    gmail_id = fields.Char(string='Gmail Message ID', required=True, index=True)
    date = fields.Datetime(string='Date', required=True)
    sender = fields.Char(string='From')
    bank_name = fields.Selection([
        ('tymebank', 'TymeBank'),
        ('capitec', 'Capitec Bank'),
        ('other', 'Other')
    ], string='Bank', compute='_compute_bank_name', store=True)
    body_html = fields.Html(string='Body HTML')
    body_text = fields.Text(string='Body Text')
    attachment_count = fields.Integer(string='Attachments', compute='_compute_attachment_count')
    transaction_ids = fields.One2many('bank.transaction', 'statement_id', string='Transaction Lines')
    transaction_count = fields.Integer(string='Transaction Count', compute='_compute_transaction_count')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('parsed', 'Parsed'),
        ('imported', 'Imported'),
    ], default='draft', string='Status')
    has_pdf = fields.Boolean(string='Has PDF', default=False)
    pdf_password = fields.Char(string='PDF Password', help='Password to unlock PDF if protected')
    parsing_log = fields.Text(string='Parsing Log', readonly=True, help='Debug information from PDF parsing')
    
    @api.depends('sender')
    def _compute_bank_name(self):
        for record in self:
            if 'tymebank' in (record.sender or '').lower():
                record.bank_name = 'tymebank'
            elif 'capitec' in (record.sender or '').lower():
                record.bank_name = 'capitec'
            else:
                record.bank_name = 'other'
    
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
    
    def action_view_attachments(self):
        """Open attachments view"""
        self.ensure_one()
        return {
            'name': 'Attachments',
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'tree,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {'default_res_model': self._name, 'default_res_id': self.id}
        }
    
    def action_download_and_parse_pdf(self):
        """Download PDF from Gmail and parse transactions"""
        for record in self:
            # Get authenticated credentials
            credentials = self.env['google.credentials'].search([
                ('is_authenticated', '=', True)
            ], limit=1)
            
            if not credentials:
                raise UserError('No authenticated Google credentials found.')
            
            # Build Gmail service
            creds = Credentials(
                token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
            )
            
            service = build('gmail', 'v1', credentials=creds)
            
            try:
                # Get the full message with attachments
                msg_data = service.users().messages().get(
                    userId='me', 
                    id=record.gmail_id
                ).execute()
                
                # Find PDF attachments
                pdf_found = False
                
                if 'parts' in msg_data['payload']:
                    for part in msg_data['payload']['parts']:
                        filename = part.get('filename', '')
                        
                        # Check if it's a PDF
                        if filename.lower().endswith('.pdf'):
                            pdf_found = True
                            _logger.info(f"Found PDF attachment: {filename}")
                            
                            # Get attachment data
                            if 'body' in part and 'attachmentId' in part['body']:
                                att_id = part['body']['attachmentId']
                                attachment = service.users().messages().attachments().get(
                                    userId='me',
                                    messageId=record.gmail_id,
                                    id=att_id
                                ).execute()
                                
                                # Decode the PDF data
                                pdf_data = base64.urlsafe_b64decode(
                                    attachment['data'].encode('UTF-8')
                                )
                                
                                # Save as Odoo attachment
                                self.env['ir.attachment'].create({
                                    'name': filename,
                                    'datas': base64.b64encode(pdf_data),
                                    'res_model': self._name,
                                    'res_id': record.id,
                                    'mimetype': 'application/pdf',
                                })
                                
                                _logger.info(f"Saved PDF: {filename}")
                                
                                # Parse PDF and extract transactions
                                record._parse_pdf_transactions(pdf_data)
                
                if pdf_found:
                    record.has_pdf = True
                    record.state = 'parsed'
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': 'Success',
                            'message': f'PDF parsed! Found {record.transaction_count} transactions. Check the Parsing Log tab for details.',
                            'type': 'success',
                        }
                    }
                else:
                    raise UserError('No PDF attachment found in this email.')
                    
            except Exception as e:
                _logger.error(f"Error downloading PDF: {str(e)}")
                raise UserError(f'Failed to download PDF: {str(e)}')
    
    def _parse_pdf_transactions(self, pdf_data):
        """Parse PDF and extract transaction data"""
        parsing_log = []
        parsing_log.append("=== PDF PARSING DEBUG LOG ===\n")
        
        try:
            # Try to import PyPDF2 or pdfplumber
            try:
                import PyPDF2
                pdf_file = io.BytesIO(pdf_data)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                
                parsing_log.append(f"Using PyPDF2, found {len(pdf_reader.pages)} pages\n")
                
                # Check if PDF is encrypted
                if pdf_reader.is_encrypted:
                    parsing_log.append("PDF is password protected\n")
                    
                    if not self.pdf_password:
                        raise UserError(
                            'This PDF is password protected. '
                            'Please enter the PDF password in the form and try again.'
                        )
                    
                    # Try to decrypt with provided password
                    decrypt_result = pdf_reader.decrypt(self.pdf_password)
                    
                    if decrypt_result == 0:
                        raise UserError(
                            'Incorrect PDF password. Please check the password and try again.'
                        )
                    else:
                        parsing_log.append("PDF decrypted successfully\n")
                
                # Extract text from all pages
                text = ""
                for i, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += page_text
                    parsing_log.append(f"\n--- Page {i+1} (first 500 chars) ---\n")
                    parsing_log.append(page_text[:500] + "...\n")
                    
            except ImportError:
                parsing_log.append("PyPDF2 not available, trying pdfplumber\n")
                try:
                    import pdfplumber
                    pdf_file = io.BytesIO(pdf_data)
                    
                    # pdfplumber also supports password
                    if self.pdf_password:
                        with pdfplumber.open(pdf_file, password=self.pdf_password) as pdf:
                            text = ""
                            for i, page in enumerate(pdf.pages):
                                page_text = page.extract_text()
                                text += page_text
                                parsing_log.append(f"\n--- Page {i+1} (first 500 chars) ---\n")
                                parsing_log.append(page_text[:500] + "...\n")
                    else:
                        with pdfplumber.open(pdf_file) as pdf:
                            text = ""
                            for i, page in enumerate(pdf.pages):
                                page_text = page.extract_text()
                                text += page_text
                                parsing_log.append(f"\n--- Page {i+1} (first 500 chars) ---\n")
                                parsing_log.append(page_text[:500] + "...\n")
                except ImportError:
                    raise UserError(
                        'PDF parsing libraries not available. '
                        'Please install PyPDF2 or pdfplumber: '
                        'pip install PyPDF2 pdfplumber'
                    )
            
            parsing_log.append(f"\n=== FULL TEXT LENGTH: {len(text)} characters ===\n")
            
            # Parse based on bank type
            parsing_log.append(f"\nBank type: {self.bank_name}\n")
            
            if self.bank_name == 'tymebank':
                transactions = self._parse_tymebank_pdf(text, parsing_log)
            elif self.bank_name == 'capitec':
                transactions = self._parse_capitec_pdf(text, parsing_log)
            else:
                transactions = self._parse_generic_pdf(text, parsing_log)
            
            parsing_log.append(f"\n=== FOUND {len(transactions)} TRANSACTIONS ===\n")
            
            # Create transaction records
            created_count = 0
            for trans in transactions:
                try:
                    parsing_log.append(f"\nCreating transaction: {trans}\n")
                    self.env['bank.transaction'].create({
                        'statement_id': self.id,
                        'date': trans.get('date'),
                        'description': trans.get('description'),
                        'amount': trans.get('amount'),
                        'transaction_type': trans.get('type'),
                        'reference': trans.get('reference'),
                    })
                    created_count += 1
                except Exception as e:
                    parsing_log.append(f"ERROR creating transaction: {str(e)}\n")
                    _logger.error(f"Failed to create transaction: {str(e)}")
            
            parsing_log.append(f"\n=== SUCCESSFULLY CREATED {created_count} TRANSACTIONS ===\n")
            
            # Save the parsing log
            self.parsing_log = ''.join(parsing_log)
            
            _logger.info(f"Created {created_count} transaction records")
            
        except UserError:
            # Save log even on user errors
            self.parsing_log = ''.join(parsing_log)
            raise
        except Exception as e:
            parsing_log.append(f"\n=== FATAL ERROR ===\n{str(e)}\n")
            self.parsing_log = ''.join(parsing_log)
            _logger.error(f"Error parsing PDF: {str(e)}")
            raise UserError(f'Failed to parse PDF: {str(e)}')
    
    def _parse_tymebank_pdf(self, text, log):
        """Parse TymeBank PDF statement"""
        transactions = []
        log.append("\n=== TRYING TYMEBANK PATTERNS ===\n")
        
        # Multiple patterns to try
        patterns = [
            # Pattern 1: 01 Oct 2024    Purchase - Shop Name    -R123.45    R1000.00
            (r'(\d{2}\s+\w{3}\s+\d{4})\s+([^\t\n]+?)\s+(-?R[\d,]+\.\d{2})\s+(R[\d,]+\.\d{2})', '%d %b %Y'),
            # Pattern 2: 2024-10-01    Description    -123.45    1000.00
            (r'(\d{4}-\d{2}-\d{2})\s+([^\t\n]+?)\s+(-?R?[\d,]+\.\d{2})\s+(R?[\d,]+\.\d{2})', '%Y-%m-%d'),
            # Pattern 3: 01/10/2024    Description    -123.45
            (r'(\d{2}/\d{2}/\d{4})\s+([^\t\n]+?)\s+(-?R?[\d,]+\.\d{2})', '%d/%m/%Y'),
        ]
        
        for pattern_idx, (pattern, date_format) in enumerate(patterns):
            log.append(f"\nTrying pattern {pattern_idx + 1}: {pattern}\n")
            matches = re.findall(pattern, text, re.MULTILINE)
            log.append(f"Found {len(matches)} matches\n")
            
            if matches:
                for match in matches:
                    try:
                        trans_date = datetime.strptime(match[0], date_format).date()
                        description = match[1].strip()
                        amount_str = match[2].replace('R', '').replace(',', '').strip()
                        amount = float(amount_str)
                        
                        transactions.append({
                            'date': trans_date,
                            'description': description,
                            'amount': abs(amount),
                            'type': 'debit' if amount < 0 else 'credit',
                            'reference': f"TYME-{trans_date.strftime('%Y%m%d')}"
                        })
                        log.append(f"✓ Parsed: {trans_date} | {description[:30]} | {amount}\n")
                    except Exception as e:
                        log.append(f"✗ Error parsing match: {str(e)}\n")
                        continue
                
                if transactions:
                    break  # Stop trying patterns if we found transactions
        
        return transactions
    
    def _parse_capitec_pdf(self, text, log):
        """Parse Capitec Bank PDF statement"""
        transactions = []
        log.append("\n=== TRYING CAPITEC PATTERNS ===\n")
        
        patterns = [
            (r'(\d{4}/\d{2}/\d{2})\s+([^\t\n]+?)\s+([^\t\n]+?)\s+(-?[\d,]+\.\d{2})\s+([\d,]+\.\d{2})', '%Y/%m/%d'),
            (r'(\d{2}/\d{2}/\d{4})\s+([^\t\n]+?)\s+(-?R?[\d,]+\.\d{2})', '%d/%m/%Y'),
        ]
        
        for pattern_idx, (pattern, date_format) in enumerate(patterns):
            log.append(f"\nTrying pattern {pattern_idx + 1}: {pattern}\n")
            matches = re.findall(pattern, text, re.MULTILINE)
            log.append(f"Found {len(matches)} matches\n")
            
            if matches:
                for match in matches:
                    try:
                        trans_date = datetime.strptime(match[0], date_format).date()
                        if len(match) >= 4:
                            trans_type = match[1].strip()
                            description = f"{trans_type} - {match[2].strip()}"
                            amount_str = match[3].replace(',', '').strip()
                        else:
                            description = match[1].strip()
                            amount_str = match[2].replace('R', '').replace(',', '').strip()
                        
                        amount = float(amount_str)
                        
                        transactions.append({
                            'date': trans_date,
                            'description': description,
                            'amount': abs(amount),
                            'type': 'debit' if amount < 0 else 'credit',
                            'reference': f"CAP-{trans_date.strftime('%Y%m%d')}"
                        })
                        log.append(f"✓ Parsed: {trans_date} | {description[:30]} | {amount}\n")
                    except Exception as e:
                        log.append(f"✗ Error parsing match: {str(e)}\n")
                        continue
                
                if transactions:
                    break
        
        return transactions
    
    def _parse_generic_pdf(self, text, log):
        """Generic PDF parsing - tries common patterns"""
        transactions = []
        log.append("\n=== TRYING GENERIC PATTERNS ===\n")
        
        # Try multiple date formats and patterns
        patterns = [
            (r'(\d{2}/\d{2}/\d{4})\s+([^\d\-\+\$R]+)\s+(-?R?[\d,]+\.\d{2})', '%d/%m/%Y'),
            (r'(\d{4}-\d{2}-\d{2})\s+([^\d\-\+\$R]+)\s+(-?R?[\d,]+\.\d{2})', '%Y-%m-%d'),
            (r'(\d{2}\s+\w{3}\s+\d{4})\s+([^\d\-\+\$R]+)\s+(-?R?[\d,]+\.\d{2})', '%d %b %Y'),
        ]
        
        for pattern_idx, (pattern, date_format) in enumerate(patterns):
            log.append(f"\nTrying generic pattern {pattern_idx + 1}\n")
            matches = re.findall(pattern, text, re.MULTILINE)
            log.append(f"Found {len(matches)} matches\n")
            
            if matches:
                for match in matches:
                    try:
                        date_str = match[0]
                        trans_date = datetime.strptime(date_str, date_format).date()
                        
                        description = match[1].strip()
                        amount_str = match[2].replace('R', '').replace(',', '').strip()
                        amount = float(amount_str)
                        
                        transactions.append({
                            'date': trans_date,
                            'description': description,
                            'amount': abs(amount),
                            'type': 'debit' if amount < 0 else 'credit',
                            'reference': f"GEN-{trans_date.strftime('%Y%m%d')}"
                        })
                        log.append(f"✓ Parsed: {trans_date} | {description[:30]} | {amount}\n")
                    except Exception as e:
                        log.append(f"✗ Error: {str(e)}\n")
                        continue
                
                if transactions:
                    break
        
        return transactions
    
    @api.model
    def fetch_statements_from_gmail(self, credential_id=None):
        """Fetch bank statements from Gmail - TymeBank and Capitec"""
        
        if not credential_id:
            credentials = self.env['google.credentials'].search([
                ('is_authenticated', '=', True)
            ], limit=1)
        else:
            credentials = self.env['google.credentials'].browse(credential_id)
        
        if not credentials:
            raise UserError('No authenticated Google credentials found. Please authenticate first.')
        
        # Build Gmail service
        try:
            creds = Credentials(
                token=credentials.access_token,
                refresh_token=credentials.refresh_token,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
            )
            
            service = build('gmail', 'v1', credentials=creds)
        except Exception as e:
            _logger.error(f"Failed to build Gmail service: {str(e)}")
            raise UserError(f'Failed to connect to Gmail: {str(e)}')
        
        # Search for both TymeBank and Capitec
        queries = [
            'from:@tymebank.co.za subject:Statement',
            'from:@capitecbank.co.za subject:Statement',
        ]
        
        all_messages = []
        
        for query in queries:
            _logger.info(f"Searching Gmail with query: {query}")
            
            try:
                results = service.users().messages().list(
                    userId='me', 
                    q=query, 
                    maxResults=50
                ).execute()
                messages = results.get('messages', [])
                all_messages.extend(messages)
                _logger.info(f"Found {len(messages)} messages for query: {query}")
                
            except Exception as e:
                _logger.error(f"Error searching Gmail: {str(e)}")
                continue
        
        if not all_messages:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Statements Found',
                    'message': 'No bank statement emails found in Gmail.',
                    'type': 'warning',
                }
            }
        
        imported_count = 0
        skipped_count = 0
        
        for msg in all_messages:
            try:
                msg_data = service.users().messages().get(
                    userId='me', 
                    id=msg['id'], 
                    format='full'
                ).execute()
                
                # Check if already imported
                existing = self.search([('gmail_id', '=', msg['id'])])
                if existing:
                    _logger.info(f"Message {msg['id']} already imported, skipping")
                    skipped_count += 1
                    continue
                
                # Extract message details
                headers = msg_data['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                _logger.info(f"Importing: {subject} from {sender}")
                
                # Parse date and convert to naive datetime
                from email.utils import parsedate_to_datetime
                try:
                    msg_date = parsedate_to_datetime(date_str)
                    if msg_date.tzinfo is not None:
                        msg_date = msg_date.astimezone(pytz.UTC).replace(tzinfo=None)
                except Exception as date_error:
                    _logger.warning(f"Error parsing date '{date_str}': {str(date_error)}")
                    msg_date = fields.Datetime.now()
                
                # Extract body
                body_html = ''
                body_text = ''
                
                if 'parts' in msg_data['payload']:
                    for part in msg_data['payload']['parts']:
                        try:
                            if part['mimeType'] == 'text/html' and 'data' in part.get('body', {}):
                                body_html = base64.urlsafe_b64decode(
                                    part['body']['data']
                                ).decode('utf-8', errors='ignore')
                            elif part['mimeType'] == 'text/plain' and 'data' in part.get('body', {}):
                                body_text = base64.urlsafe_b64decode(
                                    part['body']['data']
                                ).decode('utf-8', errors='ignore')
                        except Exception as e:
                            _logger.warning(f"Error decoding email part: {str(e)}")
                            continue
                            
                elif 'body' in msg_data['payload'] and msg_data['payload']['body'].get('data'):
                    try:
                        body_text = base64.urlsafe_b64decode(
                            msg_data['payload']['body']['data']
                        ).decode('utf-8', errors='ignore')
                    except Exception as e:
                        _logger.warning(f"Error decoding email body: {str(e)}")
                
                # Create statement record
                statement = self.create({
                    'name': subject,
                    'gmail_id': msg['id'],
                    'date': msg_date,
                    'sender': sender,
                    'body_html': body_html,
                    'body_text': body_text,
                })
                
                _logger.info(f"Created statement record ID: {statement.id}")
                
                imported_count += 1
                
            except Exception as e:
                _logger.error(f"Error importing message {msg.get('id')}: {str(e)}")
                continue
        
        _logger.info(f"Import complete: {imported_count} new, {skipped_count} skipped")
        
        message = f"Successfully imported {imported_count} statement(s)"
        if skipped_count > 0:
            message += f" ({skipped_count} already existed)"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': message,
                'type': 'success',
                'sticky': False,
            }
    }
