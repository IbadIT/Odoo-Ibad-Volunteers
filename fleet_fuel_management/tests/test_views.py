import ast

from lxml import etree

from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged

from .common import FuelLogCommon


@tagged('post_install', '-at_install')
class TestFuelViews(FuelLogCommon):

    def _action_domain(self, xml_id):
        domain = self.env.ref(xml_id).domain
        return ast.literal_eval(domain) if domain else []

    def test_consumption_report_shows_only_closed_vehicle_segments(self):
        self._fill(self.car, 0, 40.0, 10000)
        self._fill(self.car, 4, 15.0, 10300, full=False)
        closing = self._fill(self.car, 8, 30.0, 10600)
        self._fill(self.generator, 0, 100.0)
        self._fill(self.generator, 3, 90.0)
        domain = self._action_domain('fleet_fuel_management.action_fleet_fuel_consumption_report')
        found = self.env['fleet.vehicle.log.fuel'].search(
            domain + [('vehicle_id', 'in', (self.car | self.generator).ids)])
        self.assertEqual(found, closing)

    def test_cost_report_includes_generators(self):
        generator_log = self._fill(self.generator, 0, 100.0)
        car_log = self._fill(self.car, 0, 40.0, 10000)
        domain = self._action_domain('fleet_fuel_management.action_fleet_fuel_cost_report')
        found = self.env['fleet.vehicle.log.fuel'].search(domain)
        self.assertIn(generator_log, found)
        self.assertIn(car_log, found)

    def test_generators_action_lists_only_generators(self):
        domain = self._action_domain('fleet_fuel_management.action_fleet_generators')
        vehicles = self.env['fleet.vehicle'].search(domain)
        self.assertIn(self.generator, vehicles)
        self.assertNotIn(self.car, vehicles)

    def test_open_fuel_logs_from_vehicle(self):
        self._fill(self.car, 0, 40.0, 10000)
        self._fill(self.car, 8, 30.0, 10600)
        self.assertEqual(self.car.fuel_log_count, 2)
        action = self.car.action_open_fuel_logs()
        self.assertEqual(action['res_model'], 'fleet.vehicle.log.fuel')
        self.assertEqual(action['domain'], [('vehicle_id', '=', self.car.id)])
        self.assertEqual(action['context'], {'default_vehicle_id': self.car.id})

    def test_form_fills_defaults_and_amount(self):
        form = Form(self.env['fleet.vehicle.log.fuel'])
        form.vehicle_id = self.car
        form.liters = 40.0
        form.price_per_liter = 2.5
        form.odometer = 10000.0
        log = form.save()
        self.assertEqual(log.amount, 100.0)
        self.assertEqual(log.fuel_type, 'diesel')
        self.assertEqual(log.filled_by_id, self.driver.partner_id)

    def test_form_vehicle_without_odometer_is_refused(self):
        form = Form(self.env['fleet.vehicle.log.fuel'])
        form.vehicle_id = self.car
        form.liters = 40.0
        with self.assertRaises(ValidationError):
            form.save()

    def test_form_generator_saves_without_odometer(self):
        form = Form(self.env['fleet.vehicle.log.fuel'])
        form.vehicle_id = self.generator
        form.liters = 100.0
        log = form.save()
        self.assertFalse(log.odometer_id)

    def test_generator_fuel_type_is_editable_in_forms(self):
        model_form = Form(self.env['fleet.vehicle.model'])
        model_form.name = 'Form Generator'
        model_form.brand_id = self.generator_model.brand_id
        model_form.vehicle_type = 'generator'
        model_form.default_fuel_type = 'diesel'
        model = model_form.save()
        vehicle_form = Form(self.env['fleet.vehicle'])
        vehicle_form.model_id = model
        self.assertEqual(vehicle_form.fuel_type, 'diesel')
        vehicle_form.fuel_type = 'gasoline'
        vehicle = vehicle_form.save()
        log_form = Form(self.env['fleet.vehicle.log.fuel'])
        log_form.vehicle_id = vehicle
        log_form.liters = 50.0
        self.assertEqual(log_form.save().fuel_type, 'gasoline')

    def test_consumption_pivot_has_spec_measures(self):
        arch = self.env.ref('fleet_fuel_management.fleet_vehicle_log_fuel_view_pivot_consumption').arch
        measures = set(etree.fromstring(arch).xpath("//field[@type='measure']/@name"))
        self.assertEqual(measures, {'segment_km', 'segment_liters', 'consumption', 'deviation_pct'})
