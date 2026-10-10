from odoo import _, fields, models
from odoo.exceptions import ValidationError

from .fleet_vehicle import DEFAULT_TOLERANCE, TOLERANCE_PARAM


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    fuel_anomaly_tolerance = fields.Float(
        'Fuel Anomaly Tolerance (%)', config_parameter=TOLERANCE_PARAM, default=DEFAULT_TOLERANCE,
        help="A vehicle refill is flagged as abnormal when its consumption exceeds "
             "the vehicle's recent average by more than this percentage.")

    def set_values(self):
        # A Float config parameter of 0 is stored as "unset" and would silently
        # fall back to the default, so refuse it explicitly.
        if self.fuel_anomaly_tolerance <= 0:
            raise ValidationError(_("Fuel anomaly tolerance must be greater than zero."))
        params = self.env['ir.config_parameter'].sudo()
        previous = params.get_param(TOLERANCE_PARAM)
        super().set_values()
        if params.get_param(TOLERANCE_PARAM) != previous:
            # sudo: the multi-company rule would otherwise skip vehicles of unselected companies.
            self.env['fleet.vehicle'].sudo().with_context(active_test=False).search(
                [('vehicle_type', '!=', 'generator')])._fuel_recompute_segments()
