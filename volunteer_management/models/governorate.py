from odoo import models, fields


class Governorate(models.Model):
    _name = 'res.governorate'
    _description = 'Governorate'

    name = fields.Char(required=True)
