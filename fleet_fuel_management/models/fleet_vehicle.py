from odoo import _, api, fields, models
from odoo.exceptions import AccessError

TOLERANCE_PARAM = 'fleet_fuel_management.anomaly_tolerance'
DEFAULT_TOLERANCE = 20.0
# A refill is only judged once the vehicle has this many earlier closed segments...
MIN_BASELINE_SEGMENTS = 3
# ...and the baseline only looks at this many of the most recent ones.
BASELINE_WINDOW = 10


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    fuel_log_ids = fields.One2many('fleet.vehicle.log.fuel', 'vehicle_id', 'Fuel Logs')
    fuel_log_count = fields.Integer('Fuel Log Count', compute='_compute_fuel_log_count')
    avg_consumption = fields.Float(
        'Avg. Consumption (L/100km)', compute='_compute_avg_consumption', store=True)

    def _compute_fuel_log_count(self):
        counts = {
            vehicle.id: count
            for vehicle, count in self.env['fleet.vehicle.log.fuel']._read_group(
                [('vehicle_id', 'in', self.ids)], ['vehicle_id'], ['__count'])
        }
        for vehicle in self:
            vehicle.fuel_log_count = counts.get(vehicle.id, 0)

    @api.depends('fuel_log_ids.segment_km', 'fuel_log_ids.segment_liters')
    def _compute_avg_consumption(self):
        for vehicle in self:
            km = sum(vehicle.fuel_log_ids.mapped('segment_km'))
            liters = sum(vehicle.fuel_log_ids.mapped('segment_liters'))
            vehicle.avg_consumption = liters / km * 100 if km else 0.0

    def write(self, vals):
        if not self.env.su and 'avg_consumption' in vals:
            raise AccessError(_("Fuel consumption and cost figures are computed automatically and cannot be edited."))
        res = super().write(vals)
        if 'model_id' in vals:
            # The vehicle type follows the model, so it may have switched to/from generator.
            self._fuel_recompute_segments()
        return res

    def action_open_fuel_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id(
            'fleet_fuel_management.action_fleet_fuel_log')
        action['domain'] = [('vehicle_id', '=', self.id)]
        action['context'] = {'default_vehicle_id': self.id}
        return action

    def _fuel_recompute_segments(self):
        """Recompute the full-to-full segments and anomaly flags of each vehicle's fuel logs.

        A log's consumption depends on its siblings (the previous full fill),
        which ``@api.depends`` cannot express, so the whole chain is walked here.
        Runs as superuser: these are derived values that must cover every log of
        the vehicle, whatever the current user can see, and the tolerance lives in
        ``ir.config_parameter``, which only administrators may read.
        """
        tolerance = float(self.env['ir.config_parameter'].sudo().get_param(
            TOLERANCE_PARAM, DEFAULT_TOLERANCE))
        for vehicle in self.sudo():
            logs = vehicle.fuel_log_ids.sorted(lambda log: (log.date, log.odometer, log.id))
            if vehicle.vehicle_type == 'generator':
                for log in logs:
                    log._fuel_write_segment({})
                continue
            prev_full = None
            liters_since_full = 0.0
            closed = []  # (km, liters) of each closed segment, oldest first
            for log in logs:
                values = {}
                if log.odometer <= 0:
                    # Logged while the vehicle was a generator: not part of the chain.
                    log._fuel_write_segment(values)
                    continue
                if prev_full is None:
                    # Partials before the first full fill have no reference point.
                    if log.is_full_tank:
                        prev_full = log
                    log._fuel_write_segment(values)
                    continue
                liters_since_full += log.liters
                if log.is_full_tank:
                    km = log.odometer - prev_full.odometer
                    if km > 0:
                        rate = liters_since_full / km * 100
                        values = {
                            'segment_km': km,
                            'segment_liters': liters_since_full,
                            'consumption': rate,
                        }
                        window = closed[-BASELINE_WINDOW:]
                        if len(window) >= MIN_BASELINE_SEGMENTS:
                            # km-weighted, so a short segment cannot skew the baseline
                            baseline = (sum(liters for _km, liters in window)
                                        / sum(seg_km for seg_km, _liters in window) * 100)
                            deviation = (rate - baseline) / baseline * 100
                            values['deviation_pct'] = deviation
                            values['is_anomaly'] = deviation > tolerance
                        closed.append((km, liters_since_full))
                    prev_full = log
                    liters_since_full = 0.0
                log._fuel_write_segment(values)
