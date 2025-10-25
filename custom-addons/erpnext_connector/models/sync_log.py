from odoo import models, fields

class ERPNextSyncLog(models.Model):
    _name = 'erpnext.sync.log'
    _description = 'ERPNext Sync Log'
    _order = 'create_date desc'

    config_id = fields.Many2one('erpnext.config', string='Configuration')
    record_type = fields.Char(string='Record Type')
    record_id = fields.Integer(string='Record ID')
    erpnext_doctype = fields.Char(string='ERPNext DocType')
    erpnext_doc_name = fields.Char(string='ERPNext Document Name')
    status = fields.Selection([
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('pending', 'Pending')
    ], string='Status', default='pending')
    error_message = fields.Text(string='Error Message')
    sync_date = fields.Datetime(string='Sync Date', default=fields.Datetime.now)

