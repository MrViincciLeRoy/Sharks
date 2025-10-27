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
            # Delete existing transactions first
            record.transaction_ids.unlink()
            
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
                            'message': f'PDF parsed! Found {record.transaction_count} transactions.',
                            'type': 'success',
                        }
                    }
                else:
                    raise UserError('No PDF attachment found in this email.')
                    
            except Exception as e:
                _logger.error(f"Error downloading PDF: {str(e)}", exc_info=True)
                raise UserError(f'Failed to download PDF: {str(e)}')
    
    def _parse_pdf_transactions(self, pdf_data):
        """Parse PDF and extract transaction data - FIXED VERSION"""
        parsing_log = []
        parsing_log.append("=== PDF PARSING DEBUG LOG ===\n")
        
        try:
            # Try PyPDF2
            try:
                import PyPDF2
                pdf_file = io.BytesIO(pdf_data)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                
                parsing_log.append(f"Using PyPDF2, found {len(pdf_reader.pages)} pages\n")
                
                if pdf_reader.is_encrypted:
                    parsing_log.append("PDF is password protected\n")
                    if not self.pdf_password:
                        self.parsing_log = ''.join(parsing_log)
                        raise UserError('This PDF is password protected. Please enter the password and try again.')
                    
                    decrypt_result = pdf_reader.decrypt(self.pdf_password)
                    if decrypt_result == 0:
                        self.parsing_log = ''.join(parsing_log)
                        raise UserError('Incorrect PDF password.')
                    parsing_log.append("PDF decrypted successfully\n")
                
                text = ""
                for i, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    text += page_text
                    parsing_log.append(f"\n--- Page {i+1} (first 300 chars) ---\n{page_text[:300]}...\n")
                    
            except ImportError:
                parsing_log.append("PyPDF2 not available, trying pdfplumber\n")
                import pdfplumber
                pdf_file = io.BytesIO(pdf_data)
                
                with pdfplumber.open(pdf_file, password=self.pdf_password if self.pdf_password else None) as pdf:
                    text = ""
                    for i, page in enumerate(pdf.pages):
                        page_text = page.extract_text()
                        text += page_text
                        parsing_log.append(f"\n--- Page {i+1} (first 300 chars) ---\n{page_text[:300]}...\n")
            
            parsing_log.append(f"\n=== FULL TEXT LENGTH: {len(text)} characters ===\n")
            parsing_log.append(f"Bank type: {self.bank_name}\n")
            
            # Parse transactions
            if self.bank_name == 'tymebank':
                transactions = self._parse_tymebank_pdf(text, parsing_log)
            elif self.bank_name == 'capitec':
                transactions = self._parse_capitec_pdf(text, parsing_log)
            else:
                transactions = self._parse_generic_pdf(text, parsing_log)
            
            parsing_log.append(f"\n=== FOUND {len(transactions)} TRANSACTIONS ===\n")
            
            # Create transactions with detailed error handling
            created_count = 0
            failed_count = 0
            created_ids = []
            
            for idx, trans in enumerate(transactions, 1):
                try:
                    parsing_log.append(f"\n--- Transaction {idx} ---\n")
                    parsing_log.append(f"Date: {trans.get('date')}\n")
                    parsing_log.append(f"Description: {trans.get('description', '')[:50]}...\n")
                    parsing_log.append(f"Amount: {trans.get('amount')}\n")
                    parsing_log.append(f"Type: {trans.get('type')}\n")
                    
                    # Validate
                    if not trans.get('date'):
                        parsing_log.append("ERROR: Missing date\n")
                        failed_count += 1
                        continue
                    
                    if not trans.get('description'):
                        parsing_log.append("ERROR: Missing description\n")
                        failed_count += 1
                        continue
                    
                    if trans.get('amount') is None:
                        parsing_log.append("ERROR: Missing amount\n")
                        failed_count += 1
                        continue
                    
                    # Create the transaction - FIXED: No manual commit
                    new_trans = self.env['bank.transaction'].create({
                        'statement_id': self.id,
                        'date': trans['date'],
                        'description': str(trans['description'])[:500],
                        'amount': abs(float(trans['amount'])),
                        'transaction_type': trans.get('type', 'debit'),
                        'reference': str(trans.get('reference', ''))[:100],
                    })
                    
                    parsing_log.append(f"✓ Created transaction ID: {new_trans.id}\n")
                    created_ids.append(new_trans.id)
                    created_count += 1
                    
                except Exception as e:
                    parsing_log.append(f"✗ ERROR: {str(e)}\n")
                    _logger.error(f"Failed to create transaction: {str(e)}", exc_info=True)
                    failed_count += 1
            
            parsing_log.append(f"\n=== SUMMARY ===\n")
            parsing_log.append(f"Created: {created_count}\n")
            parsing_log.append(f"Failed: {failed_count}\n")
            parsing_log.append(f"Total: {len(transactions)}\n")
            parsing_log.append(f"Created IDs: {created_ids}\n")
            
            # Save log
            self.parsing_log = ''.join(parsing_log)
            
            _logger.info(f"Created {created_count} transactions: {created_ids}, {failed_count} failed")
            
            if created_count == 0:
                raise UserError(f'No transactions created. Found {len(transactions)} in PDF. Check Parsing Log.')
            
        except UserError:
            self.parsing_log = ''.join(parsing_log)
            raise
        except Exception as e:
            parsing_log.append(f"\n=== FATAL ERROR ===\n{str(e)}\n")
            import traceback
            parsing_log.append(f"\n{traceback.format_exc()}\n")
            self.parsing_log = ''.join(parsing_log)
            _logger.error(f"Parse error: {str(e)}", exc_info=True)
            raise UserError(f'Parse failed: {str(e)}')
    
    def _parse_tymebank_pdf(self, text, log):
        """Parse TymeBank PDF"""
        transactions = []
        log.append("\n=== TYMEBANK PATTERNS ===\n")
        
        patterns = [
            (r'(\d{2}\s+\w{3}\s+\d{4})\s+([^\t\n]+?)\s+(-?R[\d,]+\.\d{2})', '%d %b %Y'),
            (r'(\d{4}-\d{2}-\d{2})\s+([^\t\n]+?)\s+(-?R?[\d,]+\.\d{2})', '%Y-%m-%d'),
            (r'(\d{2}/\d{2}/\d{4})\s+([^\t\n]+?)\s+(-?R?[\d,]+\.\d{2})', '%d/%m/%Y'),
        ]
        
        for idx, (pattern, date_fmt) in enumerate(patterns, 1):
            log.append(f"\nPattern {idx}: {pattern}\n")
            matches = re.findall(pattern, text, re.MULTILINE)
            log.append(f"Matches: {len(matches)}\n")
            
            if matches:
                for match in matches:
                    try:
                        trans_date = datetime.strptime(match[0], date_fmt).date()
                        description = match[1].strip()
                        amount = float(match[2].replace('R', '').replace(',', ''))
                        
                        transactions.append({
                            'date': trans_date,
                            'description': description,
                            'amount': abs(amount),
                            'type': 'debit' if amount < 0 else 'credit',
                            'reference': f"TYME-{trans_date.strftime('%Y%m%d')}"
                        })
                        log.append(f"✓ {trans_date} | {description[:20]} | {amount}\n")
                    except Exception as e:
                        log.append(f"✗ Error: {str(e)}\n")
                        continue
                
                if transactions:
                    break
        
        return transactions
    
    def _parse_capitec_pdf(self, text, log):
        """Parse Capitec PDF"""
        transactions = []
        log.append("\n=== CAPITEC PATTERNS ===\n")
        
        patterns = [
            (r'(\d{4}/\d{2}/\d{2})\s+([^\t\n]+?)\s+(-?[\d,]+\.\d{2})', '%Y/%m/%d'),
            (r'(\d{2}/\d{2}/\d{4})\s+([^\t\n]+?)\s+(-?R?[\d,]+\.\d{2})', '%d/%m/%Y'),
        ]
        
        for idx, (pattern, date_fmt) in enumerate(patterns, 1):
            log.append(f"\nPattern {idx}\n")
            matches = re.findall(pattern, text, re.MULTILINE)
            log.append(f"Matches: {len(matches)}\n")
            
            if matches:
                for match in matches:
                    try:
                        trans_date = datetime.strptime(match[0], date_fmt).date()
                        description = match[1].strip()
                        amount = float(match[2].replace('R', '').replace(',', ''))
                        
                        transactions.append({
                            'date': trans_date,
                            'description': description,
                            'amount': abs(amount),
                            'type': 'debit' if amount < 0 else 'credit',
                            'reference': f"CAP-{trans_date.strftime('%Y%m%d')}"
                        })
                    except Exception as e:
                        log.append(f"✗ Error: {str(e)}\n")
                        continue
                
                if transactions:
                    break
        
        return transactions
    
    def _parse_generic_pdf(self, text, log):
        """Generic PDF parsing"""
        transactions = []
        log.append("\n=== GENERIC PATTERNS ===\n")
        
        patterns = [
            (r'(\d{2}/\d{2}/\d{4})\s+([^\d\-\+\$R]+)\s+(-?R?[\d,]+\.\d{2})', '%d/%m/%Y'),
            (r'(\d{4}-\d{2}-\d{2})\s+([^\d\-\+\$R]+)\s+(-?R?[\d,]+\.\d{2})', '%Y-%m-%d'),
        ]
        
        for pattern, date_fmt in patterns:
            matches = re.findall(pattern, text, re.MULTILINE)
            log.append(f"Matches: {len(matches)}\n")
            
            if matches:
                for match in matches:
                    try:
                        trans_date = datetime.strptime(match[0], date_fmt).date()
                        description = match[1].strip()
                        amount = float(match[2].replace('R', '').replace(',', ''))
                        
                        transactions.append({
                            'date': trans_date,
                            'description': description,
                            'amount': abs(amount),
                            'type': 'debit' if amount < 0 else 'credit',
                            'reference': f"GEN-{trans_date.strftime('%Y%m%d')}"
                        })
                    except:
                        continue
                
                if transactions:
                    break
        
        return transactions
    
    @api.model
    def fetch_statements_from_gmail(self, credential_id=None):
        """Fetch statements from Gmail"""
        
        if not credential_id:
            credentials = self.env['google.credentials'].search([('is_authenticated', '=', True)], limit=1)
        else:
            credentials = self.env['google.credentials'].browse(credential_id)
        
        if not credentials:
            raise UserError('No authenticated Google credentials found.')
        
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
            _logger.error(f"Gmail service failed: {str(e)}")
            raise UserError(f'Failed to connect: {str(e)}')
        
        queries = [
            'from:@tymebank.co.za subject:Statement',
            'from:@capitecbank.co.za subject:Statement',
        ]
        
        all_messages = []
        for query in queries:
            try:
                results = service.users().messages().list(userId='me', q=query, maxResults=50).execute()
                messages = results.get('messages', [])
                all_messages.extend(messages)
            except Exception as e:
                _logger.error(f"Search error: {str(e)}")
                continue
        
        if not all_messages:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Statements Found',
                    'message': 'No bank statement emails found.',
                    'type': 'warning',
                }
            }
        
        imported_count = 0
        skipped_count = 0
        
        for msg in all_messages:
            try:
                msg_data = service.users().messages().get(userId='me', id=msg['id'], format='full').execute()
                
                if self.search([('gmail_id', '=', msg['id'])]):
                    skipped_count += 1
                    continue
                
                headers = msg_data['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
                date_str = next((h['value'] for h in headers if h['name'] == 'Date'), '')
                
                from email.utils import parsedate_to_datetime
                try:
                    msg_date = parsedate_to_datetime(date_str)
                    if msg_date.tzinfo:
                        msg_date = msg_date.astimezone(pytz.UTC).replace(tzinfo=None)
                except:
                    msg_date = fields.Datetime.now()
                
                body_html = ''
                body_text = ''
                
                if 'parts' in msg_data['payload']:
                    for part in msg_data['payload']['parts']:
                        try:
                            if part['mimeType'] == 'text/html' and 'data' in part.get('body', {}):
                                body_html = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            elif part['mimeType'] == 'text/plain' and 'data' in part.get('body', {}):
                                body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        except:
                            continue
                elif 'body' in msg_data['payload'] and msg_data['payload']['body'].get('data'):
                    try:
                        body_text = base64.urlsafe_b64decode(msg_data['payload']['body']['data']).decode('utf-8', errors='ignore')
                    except:
                        pass
                
                statement = self.create({
                    'name': subject,
                    'gmail_id': msg['id'],
                    'date': msg_date,
                    'sender': sender,
                    'body_html': body_html,
                    'body_text': body_text,
                })
                
                imported_count += 1
                
            except Exception as e:
                _logger.error(f"Import error: {str(e)}")
                continue
        
        message = f"Imported {imported_count} statement(s)"
        if skipped_count > 0:
            message += f" ({skipped_count} already existed)"
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': message,
                'type': 'success',
            }
        }
