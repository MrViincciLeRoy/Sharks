from odoo import http
from odoo.http import request
import requests

class GoogleAuthController(http.Controller):
    
    @http.route('/google_auth/callback', type='http', auth='user', website=True)
    def google_auth_callback(self, code=None, state=None, **kwargs):
        """Handle OAuth callback from Google"""
        
        if not code or not state:
            return request.redirect('/web')
        
        # Get credential record
        credential = request.env['google.credentials'].browse(int(state))
        
        if not credential:
            return request.redirect('/web')
        
        # Exchange code for tokens
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        redirect_uri = f"{base_url}/google_auth/callback"
        
        token_url = 'https://oauth2.googleapis.com/token'
        data = {
            'code': code,
            'client_id': credential.client_id,
            'client_secret': credential.client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            tokens = response.json()
            
            from datetime import datetime, timedelta
            expiry = datetime.now() + timedelta(seconds=tokens.get('expires_in', 3600))
            
            credential.write({
                'access_token': tokens.get('access_token'),
                'refresh_token': tokens.get('refresh_token'),
                'token_expiry': expiry,
            })
            
            return request.redirect('/web#action=statement_email_importer.action_email_statement')
        
        return request.redirect('/web')