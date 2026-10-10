from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import FuelLogCommon


@tagged('post_install', '-at_install')
class TestFuelArabic(FuelLogCommon):

    def setUp(self):
        super().setUp()
        if not self.env['res.lang'].search([('code', '=', 'ar_001'), ('active', '=', True)]):
            self.skipTest("Arabic (ar_001) is not active on this database")

    def test_menu_and_field_labels_are_translated(self):
        menu = self.env.ref('fleet_fuel_management.menu_fleet_fuel_log')
        self.assertEqual(menu.with_context(lang='ar_001').name, 'سجلات الوقود')
        field = self.env['ir.model.fields']._get('fleet.vehicle.log.fuel', 'liters')
        self.assertEqual(field.with_context(lang='ar_001').field_description, 'اللترات')

    def test_generator_type_is_translated(self):
        selection = self.env['fleet.vehicle.model'].with_context(lang='ar_001').fields_get(
            ['vehicle_type'])['vehicle_type']['selection']
        self.assertIn(('generator', 'مولد كهربائي'), selection)

    def test_validation_message_is_translated(self):
        with self.assertRaises(ValidationError) as caught:
            self.env['fleet.vehicle.log.fuel'].with_context(lang='ar_001').create({
                'vehicle_id': self.car.id, 'liters': 0.0, 'odometer': 10000.0,
            })
        self.assertIn('اللترات', str(caught.exception))
