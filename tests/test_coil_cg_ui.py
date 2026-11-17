from pathlib import Path
import unittest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "tube_cg_calculator.py"


class AppTests(unittest.TestCase):
    def start(self):
        at = AppTest.from_file(str(APP), default_timeout=40).run()
        self.assertEqual(len(at.exception), 0)
        return at

    def test_initial_layout_has_no_supports_or_defined_cg(self):
        at = self.start()
        self.assertEqual([t.label for t in at.tabs], ["Weight distribution", "Component summary", "Calculations"])
        self.assertEqual([m.value for m in at.metric], ["0 lbf", "0 lbf", "—", "—"])
        self.assertEqual(at.session_state["cg_weight_ids"], [])
        self.assertEqual([w.label for w in at.number_input], ["Tube length (in)", "Total tube weight (lbf)"])
        self.assertFalse(any("Cross-section" in h.value for h in at.subheader))
        self.assertFalse(any("support" in w.label.lower() for w in at.number_input))
        for tab in at.tabs[:2]:
            self.assertEqual(len(tab.latex), 0)
        self.assertGreater(len(at.tabs[2].latex), 3)

    def test_point_weight_outside_tube_updates_without_calculate(self):
        at = self.start()
        at.button(key="cg_add_weight").click().run()
        at.number_input(key="cg_weight_1_magnitude").set_value(50.).run()
        at.number_input(key="cg_weight_1_position").set_value(-20.).run()
        self.assertEqual(at.metric[2].value, "-20 in")
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("beyond the tube's left end" in s.value for s in at.success))
        at.number_input(key="cg_weight_1_position").set_value(400.).run()
        self.assertEqual(at.metric[2].value, "400 in")
        self.assertTrue(any("beyond the tube's right end" in s.value for s in at.success))

    def test_switch_type_resize_and_restore_hidden_positions(self):
        at = self.start()
        at.button(key="cg_add_weight").click().run()
        at.number_input(key="cg_weight_1_position").set_value(-25.).run()
        at.radio(key="cg_weight_1_kind").set_value("Uniform weight").run()
        at.number_input(key="cg_tube_length").set_value(320.).run()
        self.assertEqual(at.number_input(key="cg_weight_1_full_end").value, 320.)
        self.assertTrue(at.number_input(key="cg_weight_1_full_end").disabled)
        at.checkbox(key="cg_weight_1_full").uncheck().run()
        at.number_input(key="cg_weight_1_start").set_value(-60.).run()
        at.number_input(key="cg_weight_1_end").set_value(-20.).run()
        at.number_input(key="cg_weight_1_magnitude").set_value(100.).run()
        self.assertEqual(at.metric[2].value, "-40 in")
        at.radio(key="cg_weight_1_kind").set_value("Point weight").run()
        self.assertEqual(at.number_input(key="cg_weight_1_position").value, -25.)
        at.radio(key="cg_weight_1_kind").set_value("Uniform weight").run()
        self.assertEqual(at.number_input(key="cg_weight_1_start").value, -60.)
        self.assertEqual(at.number_input(key="cg_weight_1_end").value, -20.)
        self.assertEqual(len(at.exception), 0)

    def test_self_weight_is_included_once_and_length_changes_cg(self):
        at = self.start()
        at.number_input(key="cg_tube_weight").set_value(370.).run()
        self.assertEqual(at.metric[0].value, "370 lbf")
        self.assertEqual(at.metric[2].value, "152.8125 in")
        at.number_input(key="cg_tube_length").set_value(400.).run()
        self.assertEqual(at.metric[2].value, "200 in")
        self.assertEqual(len(at.get("plotly_chart")), 1)

    def test_example_and_remove_weight(self):
        at = self.start()
        at.button(key="cg_load_example").click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.session_state["cg_weight_ids"], [1, 2])
        self.assertEqual(at.metric[0].value, "1,466 lbf")
        self.assertEqual(at.number_input(key="cg_weight_1_position").value, -12.)
        self.assertEqual(at.number_input(key="cg_weight_2_position").value, 323.625)
        at.button(key="cg_weight_1_remove").click().run()
        self.assertEqual(at.session_state["cg_weight_ids"], [2])
        self.assertEqual(at.metric[0].value, "416 lbf")
        self.assertEqual(len(at.exception), 0)

    def test_invalid_interval_can_be_corrected(self):
        at = self.start()
        at.button(key="cg_add_weight").click().run()
        at.radio(key="cg_weight_1_kind").set_value("Uniform weight").run()
        at.checkbox(key="cg_weight_1_full").uncheck().run()
        at.number_input(key="cg_weight_1_end").set_value(-10.).run()
        self.assertTrue(any("end must be greater" in e.value for e in at.error))
        at.number_input(key="cg_weight_1_start").set_value(-20.).run()
        self.assertEqual(len(at.error), 0)
        self.assertEqual(len(at.exception), 0)


if __name__ == "__main__":
    unittest.main()
