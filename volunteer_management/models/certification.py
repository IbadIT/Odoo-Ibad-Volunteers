from odoo import api, models, fields


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
    expiration_date = fields.Date(string='تاريخ الانتهاء')
    is_expired = fields.Boolean(string='منتهية', compute='_compute_is_expired')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'certification_attachment_rel',
        'certification_id',
        'attachment_id',
        string='الملفات'
    )

    @api.depends('expiration_date')
    def _compute_is_expired(self):
        # Not stored: the answer depends on today's date, so a stored value would go
        # stale overnight with nothing to trigger a recompute.
        today = fields.Date.context_today(self)
        for certification in self:
            expiration = certification.expiration_date
            certification.is_expired = bool(expiration) and expiration < today
