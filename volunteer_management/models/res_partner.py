from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)




class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_company= fields.Boolean(default="false")
    name_ar= fields.Char(string="Name (Arabic)")
    dob = fields.Date('Date of Birth', required=True)
    status = fields.Selection([('active', 'Active'), ('not_active', 'Not Active'), ('stopped', 'Stopped')], default='active', required=True)
    gender = fields.Selection([('male', 'Male'), ('female', 'Female')], required=True)
    veiled = fields.Selection([('veiled', 'Veiled'), ('not_veiled', 'Not Veiled')])
    take_photo = fields.Selection([('not_allowed', 'Not Allowed'), ('allowed', 'Allowed')], required=True)
    emergency_number = fields.Char(unaccent=False)
    emergency_contact_name = fields.Char(string="Emergency Contact Name")
    phone = fields.Char(required=True)
    national_nb = fields.Char(string="ID Number")
    marital_status = fields.Selection([('single', 'Single'), ('married', 'Married'), ('widowed', 'Widowed')])
    specialization = fields.Char()
    volunteering_period = fields.Selection([('seasonal', 'Seasonal'), ('permanent', 'Permanent')], required=True)
    microsoft_form = fields.Selection([('yes', 'Yes'), ('no', 'No')], required=True)
    section_id = fields.Many2one('volunteer.section', 'Volunteer Section')
    detail_id = fields.Many2one('volunteer.section.detail', 'Volunteer Section Detail')
    identification_method_id = fields.Many2one('volunteer.identification.method', 'Identification Method')
    nationality = fields.Selection([('lebanese', 'Lebanese'), ('syrian', 'Syrian'), ('palestinian', 'Palestinian') ])
    nationality_id = fields.Many2one('volunteer.nationality', string="Nationality", required=True)
    submission_form_date = fields.Datetime(string="Submission Date", readonly=True)
    is_volunteer = fields.Boolean("Is a Volunteer", default=False)
    beneficiary = fields.Selection([    ('yes', 'Yes'),  ('no', 'No'), ], string="Beneficiary", default='no')
    beneficiary_type = fields.Char(string="Beneficiary type")
    beneficiary_number = fields.Char(string="Beneficiary number")
    area = fields.Char(string="Area")
    street = fields.Char(string="Street")
    building_block = fields.Char(string="Building/Block")
    floor = fields.Char(string="Floor")
    is_in_educational_section = fields.Selection([ ('yes', 'Yes'), ('no', 'No')], string="Is Beneficiary in Educational Section?", default='no')
    educational_section_name = fields.Char(string="Section Name", required=False)
    # certificate_received= fields.Boolean(String= "Certificate Received")
    # certificate_issue_date = fields.Date( String = "Certificate Issue Date")
    # certificate_name= fields.Char(String = "Certificate Name")
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'res_partner_attachment_rel',  # Relation table name
        'partner_id',                  # Column linking to res.partner (id)
        'attachment_id',               # Column linking to ir.attachment (id)
        string='Documents',
        domain=[('res_model', '=', 'res.partner')],
        help='Attach related documents here'
    )
    certification_ids = fields.One2many(
        'res.partner.certification',
        'partner_id',
        string='Certifications'
    )



    governorate_id = fields.Many2one('res.governorate', string='Governorate')
    district_id = fields.Many2one(
        'res.district',
        string='District',
        domain="[('governorate_id', '=', governorate_id)]"
    )

    @api.onchange('governorate_id')
    def _onchange_governorate_id(self):
        if self.governorate_id:
            _logger.info(f"Governorate selected: {self.governorate_id.name}")
            self.district_id = False  # Clear old value
            return {'domain': {'district_id': [('governorate_id', '=', self.governorate_id.id)]}}
        else:
            self.district_id = False
            return {'domain': {'district_id': []}}
            
   

    
    
    @api.model
    def create(self, values):
        # Set the submission date automatically
        values['submission_form_date'] = fields.Datetime.now()
        # Check if created from the volunteers context and set is_volunteer accordingly
        if self.env.context.get('from_volunteers', False):
            values['is_volunteer'] = True
        return super(ResPartner, self).create(values)
        

    