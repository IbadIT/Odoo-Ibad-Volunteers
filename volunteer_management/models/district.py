from odoo import models, fields, api



class District(models.Model):
    _name = 'res.district'
    _description = 'District'

    name = fields.Char(required=True)
    governorate_id = fields.Many2one('res.governorate', string='Governorate', required=True)
