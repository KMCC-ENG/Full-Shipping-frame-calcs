from pathlib import Path
import csv
import io
import math
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tube_cg_calculator import Tube, Weight, solve_cg, tube_svg, plot_extent, export_csv, make_distribution


class CenterOfGravityTests(unittest.TestCase):
    def test_uniform_tube_alone_balances_at_midpoint(self):
        s = solve_cg(Tube(305.625, 370.0))
        self.assertEqual(s.cg, 152.8125)
        self.assertEqual(s.total_weight, 370)
        self.assertEqual(s.added_weight, 0)
        self.assertEqual(s.balance_residual, 0)

    def test_two_end_weights_hand_calculation(self):
        # A 100 lbf tube balances at 50 in; end weights are 100 and 300 lbf.
        # Their moments are 5,000 + 0 + 30,000 = 35,000 lbf*in.
        s = solve_cg(Tube(100, 100),
                     [Weight("Left", "point", 100, 0), Weight("Right", "point", 300, 100)])
        self.assertEqual(s.total_weight, 500)
        self.assertEqual(s.cg, 70)
        self.assertEqual(s.first_moment, 35000)

    def test_weights_beyond_both_ends_are_not_clipped(self):
        s = solve_cg(Tube(100, 100),
                     [Weight("Left", "point", 50, -20), Weight("Right", "point", 150, 130)])
        self.assertEqual(s.total_weight, 300)
        self.assertAlmostEqual(s.cg, 78.33333333333333)
        self.assertEqual(plot_extent(s), (-20, 130))
        self.assertEqual(s.components[1].moment, -1000)

    def test_uniform_interval_entirely_outside_tube(self):
        # 100*50 + 200*(-40) = -3000; total 300, CG = -10 in.
        s = solve_cg(Tube(100, 100), [Weight("Left part", "uniform", 200, -60, -20)])
        self.assertEqual(s.cg, -10)
        self.assertEqual(s.location, "Beyond left end")

    def test_cg_can_be_beyond_right_end(self):
        s = solve_cg(Tube(100, 0), [Weight("Part", "point", 40, 140)])
        self.assertEqual(s.cg, 140)
        self.assertEqual(s.location, "Beyond right end")

    def test_uniform_interval_crosses_both_ends(self):
        s = solve_cg(Tube(100, 20), [Weight("Part", "uniform", 80, -50, 150)])
        self.assertEqual(s.cg, 50)
        self.assertEqual(s.components[1].intensity, .4)
        self.assertEqual(s.total_weight, 100)

    def test_partial_uniform_weight_is_total_not_intensity(self):
        s = solve_cg(Tube(100, 100), [Weight("Part", "uniform", 50, 20, 60)])
        self.assertEqual(s.total_weight, 150)
        self.assertAlmostEqual(s.cg, 46.666666666666664)

    def test_user_previous_eight_tube_example(self):
        # 8*370 lbf uniformly over 305.625 in, with 1050/46 lbf end parts.
        s = solve_cg(Tube(305.625, 2960),
                     [Weight("Left end", "point", 1050, 0), Weight("Right end", "point", 46, 305.625)])
        self.assertEqual(s.total_weight, 4056)
        self.assertAlmostEqual(s.cg, 114.98613165680473)

    def test_reflection_reverses_the_cg(self):
        tube = Tube(100, 150)
        original = [Weight("A", "point", 50, -40), Weight("B", "uniform", 80, 30, 140)]
        reflected = [Weight("A", "point", 50, 140), Weight("B", "uniform", 80, -40, 70)]
        self.assertAlmostEqual(solve_cg(tube, reflected).cg, 100 - solve_cg(tube, original).cg)

    def test_zero_total_is_undefined(self):
        s = solve_cg(Tube(100), [Weight("Empty", "point", 0, -500)])
        self.assertIsNone(s.cg)
        self.assertIsNone(s.balance_residual)
        self.assertEqual(plot_extent(s), (0, 100))
        self.assertIn("Undefined", export_csv(s))

    def test_moment_balance_and_convex_bound(self):
        s = solve_cg(Tube(305.625, 370),
                     [Weight("A", "point", 1050, -12), Weight("B", "point", 46, 323.625),
                      Weight("C", "uniform", 125.5, -45.25, 90.125)])
        self.assertLessEqual(abs(s.balance_residual), s.balance_tolerance)
        centers = [w.center for w in s.components if w.weight > 0]
        self.assertGreaterEqual(s.cg, min(centers))
        self.assertLessEqual(s.cg, max(centers))

    def test_bad_tube_inputs_are_rejected(self):
        for tube in [Tube(0), Tube(-1), Tube(100, -1), Tube(math.inf),
                     Tube(100, math.nan), Tube(math.nan, 100)]:
            with self.subTest(tube=tube), self.assertRaises(ValueError):
                solve_cg(tube)

    def test_bad_weights_and_ranges_are_rejected(self):
        for w in [Weight("A", "point", -1, 0), Weight("A", "point", math.nan, 0),
                  Weight("A", "point", 1, math.inf), Weight("A", "uniform", 1, -10, -20),
                  Weight("A", "uniform", 1, 10, 10), Weight("A", "uniform", 1, 0),
                  Weight("A", "other", 1, 0)]:
            with self.subTest(weight=w), self.assertRaises(ValueError):
                solve_cg(Tube(100), [w])

    def test_numerical_overflow_is_rejected(self):
        with self.assertRaises(ValueError):
            solve_cg(Tube(100), [Weight("A", "point", 1e300, 1e100)])

    def test_csv_retains_negative_positions_and_moments(self):
        s = solve_cg(Tube(100, 100), [Weight("Outside", "point", 50, -20)])
        rows = list(csv.reader(io.StringIO(export_csv(s))))
        self.assertEqual(rows[2][0], "Outside")
        self.assertEqual(float(rows[2][3]), -20)
        self.assertEqual(float(rows[2][6]), -1000)
        self.assertTrue(any(r and r[0] == "Assembly CG from left end (in)" for r in rows))

    def test_svg_is_valid_escaped_and_includes_outside_coordinates(self):
        s = solve_cg(Tube(100, 100), [Weight('<part & "weight">', "point", 50, -20)])
        drawing = tube_svg(s)
        ET.fromstring(drawing)
        self.assertIn("x = -20 in", drawing)
        self.assertIn("&lt;part &amp;", drawing)
        self.assertIn("Assembly CG", drawing)
        self.assertNotIn("Fixed", drawing)

    def test_overlapping_uniform_intensities_are_summed(self):
        s = solve_cg(Tube(100),
                     [Weight("A", "uniform", 50, 0, 100), Weight("B", "uniform", 40, -20, 20)])
        fig = make_distribution(s)
        trace = fig.data[0]
        intervals = list(zip(trace.x, trace.x[1:], trace.y))
        y_at_10 = [y for left, right, y in intervals if left < 10 < right]
        self.assertEqual(y_at_10, [1.5])


if __name__ == "__main__":
    unittest.main()
