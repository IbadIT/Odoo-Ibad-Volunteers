from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import FuelLogCommon


@tagged('post_install', '-at_install')
class TestFuelLogFields(FuelLogCommon):

    def test_amount_is_liters_times_price(self):
        log = self._fill(self.car, 0, 40.0, 10000, price=2.5)
        self.assertEqual(log.amount, 100.0)

    def test_defaults_come_from_vehicle(self):
        log = self._fill(self.car, 0, 40.0, 10000)
        self.assertEqual(log.fuel_type, 'diesel')
        self.assertEqual(log.filled_by_id, self.driver.partner_id)
        self.assertEqual(log.vehicle_type, 'car')
        self.assertTrue(log.is_full_tank)
        self.assertIn(self.car.name, log.name)

    def test_log_company_follows_vehicle(self):
        other_company = self.env['res.company'].create({'name': 'Fuel Other Company'})
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.car_model.id,
            'company_id': other_company.id,
        })
        self.assertEqual(self._fill(vehicle, 0, 40.0, 10000).company_id, other_company)
        self.assertEqual(self._fill(self.car, 0, 40.0, 10000).company_id, self.car.company_id)

    def test_generator_needs_no_odometer(self):
        log = self._fill(self.generator, 0, 100.0)
        self.assertEqual(log.vehicle_type, 'generator')
        self.assertEqual(log.odometer, 0.0)


@tagged('post_install', '-at_install')
class TestFuelLogConstraints(FuelLogCommon):

    def test_liters_must_be_positive(self):
        for liters in (0.0, -5.0):
            with self.assertRaises(ValidationError):
                self._fill(self.car, 0, liters, 10000)

    def test_vehicle_requires_odometer(self):
        with self.assertRaises(ValidationError):
            self._fill(self.car, 0, 40.0, 0.0)

    def test_odometer_must_increase_with_date(self):
        self._fill(self.car, 0, 40.0, 10000)
        self._fill(self.car, 10, 30.0, 10600)
        with self.assertRaises(ValidationError):  # earlier date, higher odometer
            self._fill(self.car, 5, 20.0, 11000)
        with self.assertRaises(ValidationError):  # later date, lower odometer
            self._fill(self.car, 20, 20.0, 10500)

    def test_same_day_logs_are_not_order_checked(self):
        self._fill(self.car, 3, 30.0, 10600)
        self._fill(self.car, 3, 15.0, 10300, full=False)  # same day, lower odometer: allowed


@tagged('post_install', '-at_install')
class TestFuelLogSecurity(FuelLogCommon):

    def test_fleet_user_can_log_own_vehicle(self):
        log = self._fill(self.car, 0, 40.0, 10000, user=self.driver)
        self.assertEqual(log.vehicle_id, self.car)

    def test_fleet_user_cannot_log_other_vehicle(self):
        with self.assertRaises(AccessError):
            self._fill(self.car2, 0, 40.0, 10000, user=self.driver)

    def test_fleet_user_cannot_delete(self):
        log = self._fill(self.car, 0, 40.0, 10000)
        with self.assertRaises(AccessError):
            log.with_user(self.driver).unlink()

    def test_fleet_user_sees_only_own_vehicle_logs(self):
        own = self._fill(self.car, 0, 40.0, 10000)
        self._fill(self.car2, 0, 40.0, 10000)
        visible = self.env['fleet.vehicle.log.fuel'].with_user(self.driver).search(
            [('vehicle_id', 'in', (self.car | self.car2).ids)])
        self.assertEqual(visible, own)


@tagged('post_install', '-at_install')
class TestFuelLogOdometer(FuelLogCommon):

    def test_vehicle_log_creates_odometer_row(self):
        log = self._fill(self.car, 0, 40.0, 10000)
        self.assertTrue(log.odometer_id)
        self.assertEqual(log.odometer_id.value, 10000.0)
        self.assertEqual(log.odometer_id.date, log.date)
        self.assertEqual(log.odometer_id.vehicle_id, self.car)
        self.car.invalidate_recordset(['odometer'])
        self.assertEqual(self.car.odometer, 10000.0)

    def test_editing_log_updates_same_odometer_row(self):
        log = self._fill(self.car, 0, 40.0, 10000)
        row = log.odometer_id
        log.write({'odometer': 10100.0, 'date': self.base_date.replace(day=2)})
        self.assertEqual(log.odometer_id, row)
        self.assertEqual(row.value, 10100.0)
        self.assertEqual(row.date, self.base_date.replace(day=2))

    def test_moving_log_moves_odometer_row(self):
        log = self._fill(self.car, 0, 40.0, 10000)
        row = log.odometer_id
        log.vehicle_id = self.car2
        self.assertEqual(row.vehicle_id, self.car2)

    def test_deleting_log_removes_odometer_row(self):
        log = self._fill(self.car, 0, 40.0, 10000)
        row = log.odometer_id
        self.assertTrue(row)
        log.unlink()
        self.assertFalse(row.exists())
        self.car.invalidate_recordset(['odometer'])
        self.assertEqual(self.car.odometer, 0.0)

    def test_generator_log_has_no_odometer_row(self):
        log = self._fill(self.generator, 0, 100.0)
        self.assertFalse(log.odometer_id)
        self.assertFalse(self.env['fleet.vehicle.odometer'].search(
            [('vehicle_id', '=', self.generator.id)]))


@tagged('post_install', '-at_install')
class TestFuelLogTampering(FuelLogCommon):
    """Derived values are system-maintained: the driver the anomaly flag watches must not edit them."""

    def test_fleet_user_cannot_write_derived_fields(self):
        last = self._segments(self.car, [(7.5, 100)] * 3 + [(10.0, 100)])[-1]
        for vals in ({'is_anomaly': False}, {'deviation_pct': 0.0}, {'segment_km': 100000.0},
                     {'consumption': 1.0}, {'amount': 1.0}, {'vehicle_type': 'generator'},
                     {'odometer_id': False}):
            with self.subTest(vals=vals), self.assertRaises(AccessError):
                last.with_user(self.driver).write(vals)
        self.assertTrue(last.is_anomaly)

    def test_fleet_user_create_ignores_derived_values(self):
        log = self.env['fleet.vehicle.log.fuel'].with_user(self.driver).create({
            'vehicle_id': self.car.id, 'date': self.base_date, 'liters': 40.0,
            'odometer': 10000.0, 'price_per_liter': 2.0,
            'amount': 1.0, 'is_anomaly': True, 'consumption': 99.0,
        })
        self.assertEqual(log.amount, 80.0)
        self.assertFalse(log.is_anomaly)
        self.assertEqual(log.consumption, 0.0)

    def test_fleet_user_cannot_move_log_to_vehicle_they_do_not_drive(self):
        log = self._fill(self.car, 0, 40.0, 10000)
        with self.assertRaises(AccessError):
            log.with_user(self.driver).write({'vehicle_id': self.car2.id})
        self.assertEqual(log.vehicle_id, self.car)

    def test_fleet_user_cannot_write_vehicle_average(self):
        self._segments(self.car, [(7.5, 100)])
        with self.assertRaises(AccessError):
            self.car.with_user(self.driver).write({'avg_consumption': 0.0})
        self.assertAlmostEqual(self.car.avg_consumption, 7.5)

    def test_hiding_a_flag_leaves_a_tracking_trail(self):
        closings = self._segments(self.car, [(7.5, 100)] * 3 + [(10.0, 100), (7.5, 100)])
        flagged = closings[3]
        self.assertTrue(flagged.is_anomaly)
        # mail.thread skips tracking on records created in the same transaction;
        # run the commit hooks so the edit below behaves like a later request.
        self.env.flush_all()
        self.env.cr.precommit.run()
        flagged.with_user(self.driver).is_full_tank = False
        self.env.flush_all()
        self.env.cr.precommit.run()
        tracked = flagged.message_ids.tracking_value_ids.field_id.mapped('name')
        self.assertIn('is_full_tank', tracked)
        self.assertIn('is_anomaly', tracked)
