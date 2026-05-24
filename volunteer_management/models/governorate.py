from odoo import models, fields, api



class Governorate(models.Model):
    _name = 'res.governorate'
    _description = 'Governorate'

    name = fields.Char(required=True)
