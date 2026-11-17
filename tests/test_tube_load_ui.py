from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest

APP=Path(__file__).resolve().parents[1]/"beam_stress_calculator.py"


class AppTests(unittest.TestCase):
    def start(self):
        at=AppTest.from_file(str(APP),default_timeout=40).run()
        self.assertEqual(len(at.exception),0)
        return at

    def enter_geometry(self, at, **changes):
        values = {"tube_length": 305.625, "support_a": 100.625, "support_b_offset": 12.,
                  "tube_od": 3.96875, "tube_id": 3.219}
        for key, value in (values | changes).items():
            at.number_input(key=key).set_value(value)
        return at.run()

    def test_initial_layout_and_calculation_isolation(self):
        at=self.start()
        self.assertEqual(at.number_input(key="young_modulus").value, 29_000_000.)
        self.assertTrue(all(w.value is None for w in at.number_input if w.key != "young_modulus"))
        self.assertEqual(len(at.metric), 0)
        self.assertEqual(len(at.get("plotly_chart")), 0)
        self.assertEqual(at.session_state["force_ids"],[])
        self.enter_geometry(at)
        self.assertEqual([t.label for t in at.tabs],
                         ["Bending moment","Shear force","Deflection","Stress","Calculations"])
        self.assertEqual([m.value for m in at.metric],["—"]*4)
        for tab in at.tabs[:4]:
            self.assertEqual(len(tab.latex),0)
        self.assertGreater(len(at.tabs[4].latex),5)

    def test_add_edit_switch_remove_and_full_length_resize(self):
        at=self.start()
        at.button(key="add_force").click().run()
        self.assertEqual(at.session_state["force_ids"],[1])
        self.assertIsNone(at.number_input(key="force_1_magnitude").value)
        self.assertIsNone(at.number_input(key="force_1_position").value)
        self.enter_geometry(at)
        at.number_input(key="force_1_magnitude").set_value(370.).run()
        at.number_input(key="force_1_position").set_value(150.).run()
        self.assertEqual(len(at.exception),0)
        at.radio(key="force_1_kind").set_value("Uniform load").run()
        self.assertIsNone(at.number_input(key="force_1_start").value)
        self.assertIsNone(at.number_input(key="force_1_end").value)
        at.checkbox(key="force_1_full").check().run()
        at.number_input(key="tube_length").set_value(320.).run()
        self.assertTrue(any("From x = 0 to 320 in." in c.value for c in at.caption))
        at.checkbox(key="force_1_full").uncheck().run()
        at.number_input(key="force_1_start").set_value(20.).run()
        at.number_input(key="force_1_end").set_value(170.).run()
        at.radio(key="force_1_direction").set_value("Upward").run()
        at.radio(key="force_1_kind").set_value("Point load").run()
        self.assertEqual(at.number_input(key="force_1_position").value,150.)
        at.radio(key="force_1_kind").set_value("Uniform load").run()
        self.assertEqual(at.number_input(key="force_1_start").value,20.)
        self.assertEqual(at.number_input(key="force_1_end").value,170.)
        at.button(key="add_force").click().run()
        self.assertEqual(at.session_state["force_ids"],[1,2])
        at.button(key="force_1_remove").click().run()
        self.assertEqual(at.session_state["force_ids"],[2])
        self.assertEqual(len(at.exception),0)

    def test_worked_example_results_and_plots(self):
        at=self.start()
        self.enter_geometry(at)
        at.number_input(key="tube_weight").set_value(370.).run()
        at.button(key="add_force").click().run()
        at.number_input(key="force_1_magnitude").set_value(130.44).run()
        at.number_input(key="force_1_position").set_value(305.625).run()
        self.assertEqual(len(at.exception),0)
        self.assertIn("6,129.07",at.metric[1].value)
        self.assertEqual(len(at.get("plotly_chart")),4)
        for tab in at.tabs[:4]:
            self.assertEqual(len(tab.latex),0)
        self.assertTrue(any("all four fixed-support" in s.value for s in at.success))

    def test_reset_restores_steel_and_clears_all_inputs_forces_and_results(self):
        at = self.start()
        initial = {w.key: w.value for w in at.number_input}
        self.enter_geometry(at, young_modulus=28e6)
        at.number_input(key="allowable_stress").set_value(12000.)
        at.number_input(key="tube_weight").set_value(370.).run()
        at.button(key="add_force").click().run()
        at.number_input(key="force_1_magnitude").set_value(100.)
        at.number_input(key="force_1_position").set_value(-6.).run()
        at.button(key="add_force").click().run()
        at.radio(key="force_2_kind").set_value("Uniform load").run()
        at.radio(key="force_2_direction").set_value("Upward")
        at.number_input(key="force_2_magnitude").set_value(50.)
        at.number_input(key="force_2_start").set_value(25.)
        at.number_input(key="force_2_end").set_value(100.).run()
        self.assertEqual(at.number_input(key="young_modulus").value, 28e6)
        self.assertEqual(len(at.get("plotly_chart")), 4)

        at.button(key="reset_inputs").click().run()
        self.assertEqual({w.key: w.value for w in at.number_input}, initial)
        self.assertEqual(at.session_state["force_ids"], [])
        for key in ("force_1_position", "force_1_magnitude", "force_2_start", "force_2_kind"):
            self.assertNotIn(key, at.session_state)
        self.assertEqual(len(at.metric), 0)
        self.assertEqual(len(at.get("plotly_chart")), 0)
        self.assertEqual(len(at.get("download_button")), 0)
        self.assertEqual(len(at.exception), 0)

        at.button(key="reset_inputs").click().run()
        at.button(key="add_force").click().run()
        self.assertEqual(at.session_state["force_ids"], [1])
        self.assertIsNone(at.number_input(key="force_1_position").value)
        self.assertIsNone(at.number_input(key="force_1_magnitude").value)
        self.assertEqual(at.radio(key="force_1_direction").value, "Downward")
        at.number_input(key="young_modulus").set_value(None).run()
        at.button(key="reset_inputs").click().run()
        self.assertEqual({w.key: w.value for w in at.number_input}, initial)
        self.assertEqual(len(at.exception), 0)

    def test_fitting_loads_on_both_sides_and_clearing_required_values(self):
        at = self.start()
        self.enter_geometry(at, tube_length=120., support_a=20., support_b_offset=10.,
                            tube_od=4., tube_id=3.)
        at.button(key="add_force").click().run()
        at.number_input(key="force_1_magnitude").set_value(100.).run()
        self.assertEqual(len(at.metric), 0)
        for coordinate, expected_peak, expected_couple in [(126., "1,600.00", -600.),
                                                           (-6., "2,600.00", 600.)]:
            at.number_input(key="force_1_position").set_value(coordinate).run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn(expected_peak, at.metric[1].value)
            table = next(t.value for t in at.dataframe if "End moment, CCW + (lbf·in)" in t.value)
            self.assertEqual(table.iloc[0]["End moment, CCW + (lbf·in)"], expected_couple)
        at.number_input(key="force_1_position").set_value(None).run()
        self.assertEqual(len(at.metric), 0)
        self.assertTrue(any("Force 1" in i.value for i in at.info))
        at.number_input(key="force_1_position").set_value(0.).run()
        self.assertIn("2,000.00", at.metric[1].value)
        at.number_input(key="support_b_offset").set_value(None).run()
        self.assertEqual(len(at.tabs), 0)
        self.assertEqual(len(at.exception), 0)

    def test_uniform_load_extending_past_both_tube_ends(self):
        at = self.start()
        at.button(key="add_force").click().run()
        at.radio(key="force_1_kind").set_value("Uniform load").run()
        at.checkbox(key="force_1_full").check().run()
        self.assertEqual(len(at.exception), 0)
        at.checkbox(key="force_1_full").uncheck().run()
        self.enter_geometry(at, tube_length=100., support_a=0., support_b_offset=0., tube_id=0.)
        for key, value in [("force_1_magnitude", 120.), ("force_1_start", -10.), ("force_1_end", 110.)]:
            at.number_input(key=key).set_value(value)
        at.run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("833.33", at.metric[1].value)
        table = next(t.value for t in at.dataframe if "End moment, CCW + (lbf·in)" in t.value)
        self.assertEqual(table["End moment, CCW + (lbf·in)"].tolist(), [50., -50.])
        self.assertEqual(len(at.get("plotly_chart")), 4)


if __name__=="__main__":
    unittest.main()
