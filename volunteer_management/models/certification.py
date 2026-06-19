from odoo import models, fields


class CertificationMaster(models.Model):
    _name = 'certification.master'
    _description = 'Certification Master List'

    name = fields.Char(string='عنوان الشهادة', required=True)
    description = fields.Text(string='تفاصيل الشهادة')


class ResPartnerCertification(models.Model):
    _name = 'res.partner.certification'
    _description = 'Volunteer Certification Assignment'

    partner_id = fields.Many2one('res.partner', string='اسم المتطوع', required=True)
    certification_id = fields.Many2one('certification.master', string='عنوان الشهادة', required=True)
    issue_date = fields.Date(string='تاريخ الاصدار', required=True)
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'certification_attachment_rel',
        'certification_id',
        'attachment_id',
        string='الملفات'
    )
