from datetime import date, timedelta

from odoo.tests.common import TransactionCase, new_test_user


class FuelLogCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Pin the tolerance so a value left on the cloned DB cannot change results.
        cls.env['ir.config_parameter'].set_param('fleet_fuel_management.anomaly_tolerance', '20.0')
        # fuel_type is set explicitly on the vehicles: fleet copies the model's
        # default_fuel_type only through onchange/write, not on ORM create.
        brand = cls.env['fleet.vehicle.model.brand'].create({'name': 'Fuel Test Brand'})
        cls.car_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Fuel Test Car',
            'brand_id': brand.id,
            'vehicle_type': 'car',
            'default_fuel_type': 'diesel',
        })
        cls.generator_model = cls.env['fleet.vehicle.model'].create({
            'name': 'Fuel Test Generator',
            'brand_id': brand.id,
            'vehicle_type': 'generator',
            'default_fuel_type': 'diesel',
        })
        cls.driver = new_test_user(cls.env, login='fuel_driver', groups='fleet.fleet_group_user')
        cls.car = cls.env['fleet.vehicle'].create({
            'model_id': cls.car_model.id,
            'license_plate': 'FUEL-CAR-1',
            'fuel_type': 'diesel',
            'driver_id': cls.driver.partner_id.id,
        })
        cls.car2 = cls.env['fleet.vehicle'].create({
            'model_id': cls.car_model.id,
            'license_plate': 'FUEL-CAR-2',
            'fuel_type': 'diesel',
        })
        cls.generator = cls.env['fleet.vehicle'].create({
            'model_id': cls.generator_model.id,
            'license_plate': 'FUEL-GEN-1',
            'fuel_type': 'diesel',
        })
        cls.base_date = date(2026, 1, 1)

    def _fill(self, vehicle, day, liters, odometer=0.0, full=True, price=1.0, user=None):
        """Create a fuel log dated `day` days after base_date (as `user` if given)."""
        Log = self.env['fleet.vehicle.log.fuel']
        if user:
            Log = Log.with_user(user)
        return Log.create({
            'vehicle_id': vehicle.id,
            'date': self.base_date + timedelta(days=day),
            'liters': liters,
            'odometer': odometer,
            'is_full_tank': full,
            'price_per_liter': price,
        })

    def _segments(self, vehicle, segments, user=None):
        """Baseline full fill at 10 000 km, then one full fill per (rate L/100km, km) pair.

        Returns the closing log of each segment, oldest first.
        """
        odometer = 10000.0
        self._fill(vehicle, 0, 40.0, odometer, user=user)
        closings = []
        for day, (rate, km) in enumerate(segments, start=1):
            odometer += km
            closings.append(self._fill(vehicle, day, rate * km / 100, odometer, user=user))
        return closings
