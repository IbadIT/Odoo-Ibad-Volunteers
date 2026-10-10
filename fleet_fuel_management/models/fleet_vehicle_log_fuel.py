from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.fleet.models.fleet_vehicle_model import FUEL_TYPES

# Writing any of these re-syncs the log's fleet.vehicle.odometer row.
ODOMETER_FIELDS = {'odometer', 'date', 'vehicle_id'}
# Writing any of these re-walks the vehicle's full-to-full segments.
SEGMENT_TRIGGER_FIELDS = {'vehicle_id', 'date', 'odometer', 'liters', 'is_full_tank'}
# Values of a log that does not close a segment.
SEGMENT_DEFAULTS = {
    'segment_km': 0.0,
    'segment_liters': 0.0,
    'consumption': 0.0,
    'deviation_pct': 0.0,
    'is_anomaly': False,
}
# System-maintained values: only the recompute and odometer sync (run as superuser)
# may write them; readonly=True alone does not stop an RPC write.
PROTECTED_FIELDS = set(SEGMENT_DEFAULTS) | {'odometer_id', 'amount', 'vehicle_type', 'manager_id'}


class FleetVehicleLogFuel(models.Model):
    _name = 'fleet.vehicle.log.fuel'
    _inherit = ['mail.thread']
    _description = 'Fuel Log'
    _order = 'date desc, odometer desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehicle', required=True, index=True, tracking=True)
    vehicle_type = fields.Selection(related='vehicle_id.vehicle_type', store=True)
    date = fields.Date(required=True, default=fields.Date.context_today, tracking=True)
    liters = fields.Float(required=True, tracking=True)
    price_per_liter = fields.Monetary('Price per Liter', tracking=True)
    amount = fields.Monetary('Total Cost', compute='_compute_amount', store=True)
    company_id = fields.Many2one(
        'res.company', 'Company', compute='_compute_company_id', store=True, readonly=False)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    fuel_type = fields.Selection(
        FUEL_TYPES, 'Fuel Type', compute='_compute_fuel_type', store=True, readonly=False)
    vendor_id = fields.Many2one('res.partner', 'Supplier / Station')
    filled_by_id = fields.Many2one(
        'res.partner', 'Filled By', compute='_compute_filled_by_id', store=True, readonly=False)
    is_full_tank = fields.Boolean('Full Tank', default=True, tracking=True)
    odometer = fields.Float('Odometer Value', tracking=True)
    odometer_unit = fields.Selection(related='vehicle_id.odometer_unit', string='Unit')
    odometer_id = fields.Many2one(
        'fleet.vehicle.odometer', 'Odometer Log', readonly=True, copy=False, ondelete='set null')
    segment_km = fields.Float('Segment Distance', readonly=True, copy=False)
    segment_liters = fields.Float('Segment Liters', readonly=True, copy=False)
    consumption = fields.Float(
        'Consumption (L/100km)', readonly=True, copy=False, group_operator='avg')
    deviation_pct = fields.Float('Deviation (%)', readonly=True, copy=False, group_operator='avg')
    is_anomaly = fields.Boolean('Abnormal Consumption', readonly=True, copy=False, tracking=True)
    manager_id = fields.Many2one(related='vehicle_id.manager_id', store=True)
    notes = fields.Text()

    @api.depends('vehicle_id.name', 'date')
    def _compute_name(self):
        for log in self:
            log.name = ' / '.join(filter(None, [log.vehicle_id.name, log.date and str(log.date)]))

    @api.depends('liters', 'price_per_liter')
    def _compute_amount(self):
        for log in self:
            log.amount = log.liters * log.price_per_liter

    @api.depends('vehicle_id')
    def _compute_company_id(self):
        for log in self:
            log.company_id = log.vehicle_id.company_id or self.env.company

    @api.depends('vehicle_id')
    def _compute_fuel_type(self):
        for log in self:
            log.fuel_type = log.vehicle_id.fuel_type

    @api.depends('vehicle_id')
    def _compute_filled_by_id(self):
        for log in self:
            log.filled_by_id = log.vehicle_id.driver_id

    @api.model_create_multi
    def create(self, vals_list):
        logs = super().create(vals_list)
        logs._sync_odometer()
        logs.vehicle_id._fuel_recompute_segments()
        return logs

    def write(self, vals):
        if not self.env.su and PROTECTED_FIELDS & vals.keys():
            raise AccessError(_("Fuel consumption and cost figures are computed automatically and cannot be edited."))
        vehicles_before = self.vehicle_id
        res = super().write(vals)
        if 'vehicle_id' in vals:
            # Record rules are only checked against the old vehicle: re-check the new one.
            self.check_access_rule('write')
        if ODOMETER_FIELDS & vals.keys():
            self._sync_odometer()
        if SEGMENT_TRIGGER_FIELDS & vals.keys():
            (vehicles_before | self.vehicle_id)._fuel_recompute_segments()
        return res

    def unlink(self):
        vehicles = self.vehicle_id
        odometers = self.odometer_id
        res = super().unlink()
        odometers.unlink()
        vehicles._fuel_recompute_segments()
        return res

    def _sync_odometer(self):
        """Keep one fleet.vehicle.odometer row per vehicle fuel log, mirroring its value and date.

        Per record on purpose: fleet's own _set_odometer assigns ``self.odometer_id``
        inside its loop, linking every record to the last row.
        """
        for log in self:
            if log.vehicle_type == 'generator' or log.odometer <= 0:
                stale = log.odometer_id
                if stale:
                    log.sudo().odometer_id = False
                    stale.unlink()
                continue
            vals = {'value': log.odometer, 'date': log.date, 'vehicle_id': log.vehicle_id.id}
            if log.odometer_id:
                log.odometer_id.write(vals)
            else:
                log.sudo().odometer_id = self.env['fleet.vehicle.odometer'].create(vals)

    def _fuel_write_segment(self, values):
        """Write segment/anomaly values (keys not given are reset); skip if nothing changed.

        The keys are not in SEGMENT_TRIGGER_FIELDS, so this write does not recurse
        into another recompute.
        """
        self.ensure_one()
        new_values = {**SEGMENT_DEFAULTS, **values}
        changed = {name: value for name, value in new_values.items() if self[name] != value}
        if changed:
            self.write(changed)

    @api.constrains('liters')
    def _check_liters(self):
        for log in self:
            if log.liters <= 0:
                raise ValidationError(_("Liters must be greater than zero."))

    @api.constrains('odometer', 'vehicle_id')
    def _check_odometer_required(self):
        for log in self:
            if log.vehicle_type != 'generator' and log.odometer <= 0:
                raise ValidationError(_("Odometer is required for vehicle %s.", log.vehicle_id.name))

    @api.constrains('odometer', 'date', 'vehicle_id')
    def _check_odometer_date_order(self):
        for log in self.filtered(lambda l: l.vehicle_type != 'generator'):
            conflict = self.sudo().search([
                ('vehicle_id', '=', log.vehicle_id.id),
                ('id', '!=', log.id),
                '|',
                '&', ('date', '<', log.date), ('odometer', '>', log.odometer),
                '&', ('date', '>', log.date), ('odometer', '<', log.odometer),
            ], limit=1)
            if conflict:
                raise ValidationError(_(
                    "Odometer %(odometer)s on %(date)s conflicts with the fuel log of "
                    "%(other_date)s (odometer %(other_odometer)s): odometer must increase with date.",
                    odometer=log.odometer, date=log.date,
                    other_date=conflict.date, other_odometer=conflict.odometer,
                ))
