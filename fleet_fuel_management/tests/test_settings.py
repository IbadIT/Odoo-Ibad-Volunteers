from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import FuelLogCommon


@tagged('post_install', '-at_install')
class TestFuelSettings(FuelLogCommon):

    def _set_tolerance(self, value):
        self.env['res.config.settings'].create({'fuel_anomaly_tolerance': value}).set_values()

    def test_changing_tolerance_reflags_existing_logs(self):
        last = self._segments(self.car, [(7.5, 100)] * 3 + [(10.0, 100)])[-1]  # +33.3%
        self.assertTrue(last.is_anomaly)
        self._set_tolerance(50.0)
        self.assertFalse(last.is_anomaly)
        self._set_tolerance(20.0)
        self.assertTrue(last.is_anomaly)

    def test_tolerance_must_be_positive(self):
        for value in (0.0, -5.0):
            with self.assertRaises(ValidationError):
                self._set_tolerance(value)

    def test_settings_show_stored_tolerance(self):
        self._set_tolerance(35.0)
        self.assertEqual(self.env['res.config.settings'].create({}).fuel_anomaly_tolerance, 35.0)

    def test_missing_parameter_falls_back_to_default(self):
        self.env['ir.config_parameter'].set_param('fleet_fuel_management.anomaly_tolerance', False)
        last = self._segments(self.car, [(7.5, 100)] * 3 + [(9.5, 100)])[-1]  # +26.7% > 20
        self.assertTrue(last.is_anomaly)

    def test_tolerance_change_recomputes_vehicles_of_all_companies(self):
        other_company = self.env['res.company'].create({'name': 'Fuel Other Company'})
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.car_model.id, 'company_id': other_company.id,
        })
        last = self._segments(vehicle, [(7.5, 100)] * 3 + [(10.0, 100)])[-1]  # +33.3%
        self.assertTrue(last.is_anomaly)
        admin = self.env.ref('base.user_admin')  # a real administrator, not the superuser
        self.env['res.config.settings'].with_user(admin).with_context(
            allowed_company_ids=admin.company_id.ids,
        ).create({'fuel_anomaly_tolerance': 50.0}).set_values()
        self.assertFalse(last.is_anomaly)
