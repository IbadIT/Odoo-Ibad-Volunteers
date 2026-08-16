import re
import unicodedata

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

TATWEEL = 'ـ'
ARABIC_LETTER_FOLD = {
    'ى': 'ي',  # alef maqsura -> yeh
    'ة': 'ه',  # teh marbuta  -> heh
    'ٱ': 'ا',  # alef wasla   -> alef
}
ARABIC_DIGIT_FOLD = {chr(0x0660 + i): str(i) for i in range(10)}
ARABIC_DIGIT_FOLD.update({chr(0x06F0 + i): str(i) for i in range(10)})


def normalize_name(value):
    """Fold a name to the form used for uniqueness comparison.

    Arabic is typed inconsistently: hamza may be omitted (أهل / اهل), tashkeel and
    tatweel are decorative, and teh marbuta is often written as heh. Decomposing to
    NFD and dropping the combining marks folds every hamza form and every haraka in
    one pass; the remaining letters have no decomposition and are mapped explicitly.
    """
    if not value:
        return ''
    text = unicodedata.normalize('NFD', value)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = text.replace(TATWEEL, '')
    text = ''.join(ARABIC_LETTER_FOLD.get(c, ARABIC_DIGIT_FOLD.get(c, c)) for c in text)
    return re.sub(r'\s+', ' ', text).strip().lower()


def check_unique_name(records):
    """Reject records whose name matches another record of the same model."""
    if not records:
        return
    index = {}
    for existing in records.browse().sudo().search([]):
        index.setdefault(normalize_name(existing.name), []).append(existing)
    for record in records:
        key = normalize_name(record.name)
        if not key:
            continue
        conflicts = [r for r in index.get(key, []) if r.id != record.id]
        if conflicts:
            raise ValidationError(_(
                'This %(model)s already exists as "%(existing)s". '
                'Names must be unique, ignoring hamza, tashkeel, tatweel and spacing differences.',
                model=records._description,
                existing=conflicts[0].name,
            ))


def rtn_valid_records(record_ids):
    return record_ids.filtered(lambda r: not r.from_xml and not r.partner_ids)


class VolunteerSection(models.Model):
    _name = 'volunteer.section'
    _description = 'Volunteer Section'

    name = fields.Char(required=True)
    partner_ids = fields.One2many('res.partner', 'section_id')
    from_xml = fields.Boolean(default=False)

    @api.constrains('name')
    def _check_unique_name(self):
        check_unique_name(self)

    def unlink(self):
        if self.partner_ids:
            raise ValidationError('Cannot delete section linked to volunteer')
        return super(VolunteerSection, rtn_valid_records(self)).unlink()


class VolunteerSectionDetail(models.Model):
    _name = 'volunteer.section.detail'
    _description = 'Volunteer Section Detail'

    name = fields.Char(required=True)
    partner_ids = fields.One2many('res.partner', 'detail_id')
    from_xml = fields.Boolean(default=False)

    @api.constrains('name')
    def _check_unique_name(self):
        check_unique_name(self)

    def unlink(self):
        if self.partner_ids:
            raise ValidationError('Cannot delete section detail linked to volunteer')
        return super(VolunteerSectionDetail, rtn_valid_records(self)).unlink()


class VolunteerIdentificationMethod(models.Model):
    _name = 'volunteer.identification.method'
    _description = 'Volunteer Identification Method'

    name = fields.Char(required=True)
    partner_ids = fields.One2many('res.partner', 'identification_method_id')
    from_xml = fields.Boolean(default=False)

    @api.constrains('name')
    def _check_unique_name(self):
        check_unique_name(self)

    def unlink(self):
        if self.partner_ids:
            raise ValidationError('Cannot delete identification method linked to volunteer')
        return super(VolunteerIdentificationMethod, rtn_valid_records(self)).unlink()


class VolunteerNationality(models.Model):
    _name = 'volunteer.nationality'
    _description = 'Volunteer Nationality'

    name = fields.Char(required=True)
    partner_ids = fields.One2many('res.partner', 'nationality')
    from_xml = fields.Boolean(default=False)

    @api.constrains('name')
    def _check_unique_name(self):
        check_unique_name(self)

    def unlink(self):
        if self.partner_ids:
            raise ValidationError('Cannot delete identification method linked to volunteer')
        return super(VolunteerNationality, rtn_valid_records(self)).unlink()
