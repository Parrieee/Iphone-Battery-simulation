"""Tests for the battery calculator. Run with:  python3 -m unittest"""

import unittest

from battery_model import Battery, format_duration, state_for


class StateTests(unittest.TestCase):
    def test_state_thresholds(self):
        self.assertEqual(state_for(100), "healthy")
        self.assertEqual(state_for(21), "healthy")
        self.assertEqual(state_for(20), "low")
        self.assertEqual(state_for(11), "low")
        self.assertEqual(state_for(10), "critical")
        self.assertEqual(state_for(0), "critical")

    def test_format_duration(self):
        self.assertEqual(format_duration(0.75), "45 min")
        self.assertEqual(format_duration(3 + 20 / 60), "3 h 20 min")
        self.assertEqual(format_duration(None), "—")


class DrainTests(unittest.TestCase):
    def setUp(self):
        self.b = Battery()

    def test_baseline_drain(self):
        # standby 1 + screen 2 + backlight 4*0.5 + 4 apps * 0.35 = 6.4 %/h
        self.assertAlmostEqual(self.b.drain_rate(50, 4, 25, 100), 6.4)

    def test_more_load_drains_faster(self):
        base = self.b.drain_rate(50, 5, 25, 100)
        self.assertGreater(self.b.drain_rate(100, 5, 25, 100), base)
        self.assertGreater(self.b.drain_rate(50, 15, 25, 100), base)
        self.assertGreater(self.b.drain_rate(50, 5, -5, 100), base)
        self.assertGreater(self.b.drain_rate(50, 5, 42, 100), base)
        self.assertGreater(self.b.drain_rate(50, 5, 25, 80), base)

    def test_low_power_saves_30_percent(self):
        normal = self.b.drain_rate(70, 5, 25, 100, low_power=False)
        saving = self.b.drain_rate(70, 5, 25, 100, low_power=True)
        self.assertAlmostEqual(saving, normal * 0.7)

    def test_dead_battery_does_not_drain(self):
        self.b.level = 0
        self.assertEqual(self.b.drain_rate(100, 20, 25, 100), 0.0)

    def test_hours_left_matches_rate(self):
        self.b.level = 50
        drain = self.b.drain_rate(50, 4, 25, 100)
        self.assertAlmostEqual(self.b.hours_left(drain, False, 25), 50 / drain)


class ChargeTests(unittest.TestCase):
    def setUp(self):
        self.b = Battery()

    def test_charge_curve_slows_down(self):
        rates = []
        for level in (50, 85, 97):
            self.b.level = level
            rates.append(self.b.charge_rate(25))
        self.assertEqual(rates, [60.0, 20.0, 8.0])

    def test_charging_pauses_when_hot(self):
        self.b.level = 50
        self.assertEqual(self.b.charge_rate(41), 0.0)
        self.assertTrue(self.b.charging_paused_hot)
        self.assertIsNone(self.b.hours_left(5.0, True, 41))

    def test_level_stays_between_0_and_100(self):
        self.b.step(10, 50, False, 25)
        self.assertEqual(self.b.level, 0.0)
        self.b.step(10, 0, True, 25)
        self.assertEqual(self.b.level, 100.0)


class LowPowerTests(unittest.TestCase):
    def test_turns_on_at_20_and_off_at_80_while_charging(self):
        b = Battery()
        b.level = 21
        b.step(1 / 60, 60, False, 25)       # drops 1% to 20%
        self.assertTrue(b.low_power)
        b.step(1, 0, True, 25)              # +60% to 80%
        self.assertFalse(b.low_power)

    def test_user_can_turn_it_off_and_it_stays_off(self):
        b = Battery()
        b.level = 19
        b.step(0.01, 1, False, 25)
        self.assertTrue(b.low_power)
        b.low_power = False                 # the user switches it off
        b.step(0.01, 1, False, 25)
        self.assertFalse(b.low_power)

    def test_history_records_each_minute(self):
        b = Battery()
        for _ in range(10):
            b.step(1 / 60, 6, False, 25)
        self.assertEqual(len(b.history), 11)


if __name__ == "__main__":
    unittest.main()
