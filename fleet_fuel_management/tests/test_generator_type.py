from odoo.tests import tagged

from .common import FuelLogCommon


@tagged('post_install', '-at_install')
class TestGeneratorType(FuelLogCommon):

    def test_generator_is_a_vehicle_type(self):
        selection = dict(self.env['fleet.vehicle.model']._fields['vehicle_type'].selection)
        self.assertEqual(selection.get('generator'), 'Generator')
        self.assertEqual(self.generator.vehicle_type, 'generator')
        self.assertEqual(self.car.vehicle_type, 'car')
