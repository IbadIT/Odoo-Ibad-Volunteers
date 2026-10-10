from odoo.tests import tagged

from .common import FuelLogCommon


@tagged('post_install', '-at_install')
class TestFuelSegments(FuelLogCommon):

    def _worked_example(self):
        """Spec example: full 10 000 → partial 10 300 (15 L) → full 10 600 (30 L)."""
        first = self._fill(self.car, 0, 40.0, 10000)
        partial = self._fill(self.car, 4, 15.0, 10300, full=False)
        closing = self._fill(self.car, 8, 30.0, 10600)
        return first, partial, closing

    def test_full_partial_full_computes_consumption(self):
        first, partial, closing = self._worked_example()
        self.assertAlmostEqual(closing.segment_km, 600.0)
        self.assertAlmostEqual(closing.segment_liters, 45.0)
        self.assertAlmostEqual(closing.consumption, 7.5)
        for log in first | partial:
            self.assertEqual(log.segment_km, 0.0)
            self.assertEqual(log.consumption, 0.0)
        self.assertAlmostEqual(self.car.avg_consumption, 7.5)

    def test_partials_before_first_full_are_ignored(self):
        self._fill(self.car, 0, 20.0, 9800, full=False)
        first = self._fill(self.car, 1, 40.0, 10000)
        closing = self._fill(self.car, 5, 30.0, 10400)
        self.assertEqual(first.consumption, 0.0)
        self.assertAlmostEqual(closing.segment_liters, 30.0)
        self.assertAlmostEqual(closing.consumption, 7.5)

    def test_full_fills_at_same_odometer_close_no_segment(self):
        self._fill(self.car, 0, 40.0, 10000)
        top_up = self._fill(self.car, 0, 5.0, 10000)
        self.assertEqual(top_up.segment_km, 0.0)
        self.assertEqual(top_up.consumption, 0.0)
        closing = self._fill(self.car, 5, 30.0, 10400)
        self.assertAlmostEqual(closing.segment_km, 400.0)  # measured from the top-up
        self.assertAlmostEqual(closing.consumption, 7.5)

    def test_same_day_fills_follow_odometer_order(self):
        self._fill(self.car, 0, 40.0, 10000)
        closing = self._fill(self.car, 3, 30.0, 10600)
        self._fill(self.car, 3, 15.0, 10300, full=False)  # same day, entered after the full
        self.assertAlmostEqual(closing.segment_liters, 45.0)
        self.assertAlmostEqual(closing.consumption, 7.5)

    def test_editing_partial_liters_recomputes(self):
        _first, partial, closing = self._worked_example()
        partial.liters = 25.0
        self.assertAlmostEqual(closing.consumption, 55.0 / 600 * 100)

    def test_deleting_partial_recomputes(self):
        _first, partial, closing = self._worked_example()
        partial.unlink()
        self.assertAlmostEqual(closing.segment_liters, 30.0)
        self.assertAlmostEqual(closing.consumption, 5.0)

    def test_moving_log_recomputes_both_vehicles(self):
        self._fill(self.car, 0, 40.0, 10000)
        closing = self._fill(self.car, 8, 30.0, 10600)
        self._fill(self.car2, 0, 50.0, 10200)
        closing.vehicle_id = self.car2
        self.assertAlmostEqual(closing.segment_km, 400.0)
        self.assertAlmostEqual(closing.consumption, 7.5)
        self.assertEqual(self.car.avg_consumption, 0.0)
        self.assertAlmostEqual(self.car2.avg_consumption, 7.5)

    def test_backdated_insert_recomputes(self):
        self._fill(self.car, 0, 40.0, 10000)
        closing = self._fill(self.car, 8, 30.0, 10600)
        self.assertAlmostEqual(closing.consumption, 5.0)
        self._fill(self.car, 4, 15.0, 10300, full=False)
        self.assertAlmostEqual(closing.consumption, 7.5)

    def test_avg_consumption_is_km_weighted(self):
        self._fill(self.car, 0, 40.0, 10000)
        self._fill(self.car, 8, 45.0, 10600)   # 600 km, 7.5 L/100km
        self._fill(self.car, 10, 20.0, 10700)  # 100 km, 20 L/100km
        # weighted: 65 L / 700 km; an unweighted mean would be 13.75
        self.assertAlmostEqual(self.car.avg_consumption, 65.0 / 700 * 100)

    def test_generator_logs_get_no_segments(self):
        logs = self._fill(self.generator, 0, 100.0) | self._fill(self.generator, 5, 80.0)
        self.assertEqual(logs.mapped('segment_km'), [0.0, 0.0])
        self.assertEqual(logs.mapped('consumption'), [0.0, 0.0])
        self.assertEqual(self.generator.avg_consumption, 0.0)

    def test_switching_generator_to_car_ignores_generator_logs(self):
        vehicle = self.env['fleet.vehicle'].create({
            'model_id': self.generator_model.id, 'license_plate': 'FUEL-SWITCH',
        })
        self._fill(vehicle, 0, 100.0)
        self._fill(vehicle, 2, 80.0)
        vehicle.model_id = self.car_model
        first_car_fill = self._fill(vehicle, 5, 40.0, 10000)
        closing = self._fill(vehicle, 10, 30.0, 10600)
        self.assertEqual(first_car_fill.segment_km, 0.0)  # not a 10 000 km segment from odometer 0
        self.assertAlmostEqual(closing.consumption, 5.0)
        self.assertAlmostEqual(vehicle.avg_consumption, 5.0)

    def test_switching_car_to_generator_clears_segments(self):
        self._fill(self.car, 0, 40.0, 10000)
        closing = self._fill(self.car, 8, 30.0, 10600)
        self.assertAlmostEqual(closing.consumption, 5.0)
        self.car.model_id = self.generator_model
        self.assertEqual(closing.consumption, 0.0)
        self.assertEqual(self.car.avg_consumption, 0.0)

    def test_fleet_user_save_computes_consumption(self):
        self._fill(self.car, 0, 40.0, 10000, user=self.driver)
        closing = self._fill(self.car, 8, 30.0, 10600, user=self.driver)
        self.assertAlmostEqual(closing.consumption, 5.0)


@tagged('post_install', '-at_install')
class TestFuelAnomaly(FuelLogCommon):

    def test_high_consumption_is_flagged(self):
        last = self._segments(self.car, [(7.5, 100)] * 3 + [(10.0, 100)])[-1]
        self.assertTrue(last.is_anomaly)
        self.assertAlmostEqual(last.deviation_pct, 33.333, places=2)

    def test_low_consumption_is_not_flagged(self):
        last = self._segments(self.car, [(7.5, 100)] * 3 + [(5.0, 100)])[-1]
        self.assertFalse(last.is_anomaly)
        self.assertAlmostEqual(last.deviation_pct, -33.333, places=2)

    def test_within_tolerance_is_not_flagged(self):
        last = self._segments(self.car, [(7.5, 100)] * 3 + [(8.5, 100)])[-1]  # +13.3%
        self.assertFalse(last.is_anomaly)

    def test_no_flag_without_three_prior_segments(self):
        closings = self._segments(self.car, [(7.5, 100), (7.5, 100), (50.0, 100)])
        self.assertFalse(closings[-1].is_anomaly)
        self.assertEqual(closings[-1].deviation_pct, 0.0)

    def test_baseline_uses_last_ten_segments(self):
        # One huge early segment, then ten normal ones. The window drops the
        # outlier, so 9.5 is judged against 7.5 (+26.7%). A lifetime average
        # (15.9) would hide it.
        last = self._segments(self.car, [(100.0, 100)] + [(7.5, 100)] * 10 + [(9.5, 100)])[-1]
        self.assertAlmostEqual(last.deviation_pct, 26.667, places=2)
        self.assertTrue(last.is_anomaly)

    def test_baseline_is_km_weighted(self):
        # Weighted baseline = (22.5 + 22.5 + 15) L / 650 km = 9.23 → 12.0 is +30%.
        # An unweighted mean (15.0) would put 12.0 at -20% and miss it.
        last = self._segments(self.car, [(7.5, 300), (7.5, 300), (30.0, 50), (12.0, 100)])[-1]
        self.assertAlmostEqual(last.deviation_pct, 30.0, places=2)
        self.assertTrue(last.is_anomaly)

    def test_flag_clears_when_liters_corrected(self):
        last = self._segments(self.car, [(7.5, 100)] * 3 + [(10.0, 100)])[-1]
        self.assertTrue(last.is_anomaly)
        last.liters = 7.5
        self.assertFalse(last.is_anomaly)
        self.assertAlmostEqual(last.deviation_pct, 0.0)

    def test_generator_is_never_flagged(self):
        logs = self._fill(self.generator, 0, 10.0) | self._fill(self.generator, 1, 500.0)
        self.assertEqual(logs.mapped('is_anomaly'), [False, False])

    def test_fleet_user_save_runs_anomaly_check(self):
        last = self._segments(self.car, [(7.5, 100)] * 3 + [(10.0, 100)], user=self.driver)[-1]
        self.assertTrue(last.is_anomaly)
