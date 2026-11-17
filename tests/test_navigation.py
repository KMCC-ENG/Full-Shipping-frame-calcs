"""Exercise the combined app through the same buttons a user clicks."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "app.py"
NAMES = ["Coil Center of Gravity", "Tube Load Analyzer", "Shipping Frame Load Analyzer"]


def start():
    app = AppTest.from_file(str(APP), default_timeout=90).run()
    assert [button.label for button in app.button] == NAMES
    assert not app.exception
    return app


def click(app, key):
    app.button(key=key).click().run()
    assert not app.exception


def metrics(app):
    return [(m.label, m.value) for m in app.metric]


def test_partly_entered_tube_survives_immediate_home_and_changes_to_coil():
    app = start()
    click(app, "open_tube_load")
    click(app, "add_force")
    app.number_input(key="tube_length").set_value(304.5)
    app.number_input(key="force_1_magnitude").set_value(130.44)
    # Send Home with the field edits, without an intervening Calculate or rerun.
    click(app, "suite_home")
    click(app, "open_tube_load")
    assert app.number_input(key="tube_length").value == 304.5
    assert app.number_input(key="force_1_magnitude").value == 130.44
    assert app.number_input(key="force_1_position").value is None
    assert app.number_input(key="support_a").value is None

    click(app, "suite_home")
    click(app, "open_coil_cg")
    click(app, "cg_add_weight")
    app.number_input(key="cg_tube_length").set_value(120.)
    app.number_input(key="cg_tube_weight").set_value(24.)
    app.text_input(key="cg_weight_1_name").set_value("Left fitting")
    app.number_input(key="cg_weight_1_magnitude").set_value(16.)
    app.number_input(key="cg_weight_1_position").set_value(-10.)
    app.run()
    assert app.metric[2].value == "32 in"
    click(app, "suite_home")
    click(app, "open_tube_load")
    assert app.number_input(key="tube_length").value == 304.5
    assert app.number_input(key="force_1_magnitude").value == 130.44
    click(app, "reset_inputs")
    click(app, "suite_home")
    click(app, "open_coil_cg")
    assert app.number_input(key="cg_tube_length").value == 120.
    assert app.text_input(key="cg_weight_1_name").value == "Left fitting"
    assert app.metric[2].value == "32 in"


def test_calculated_frame_and_tube_keep_their_results_after_using_all_three():
    app = start()
    click(app, "open_shipping_frame")
    click(app, "sf_disclaimer_ok")
    click(app, "sf_load_example")
    app.number_input(key="sf_mesh").set_value(16).run()
    click(app, "sf_calculate")
    frame_metrics = metrics(app)
    frame_digest = app.session_state.sf_solution_digest
    assert len(frame_metrics) == 4

    click(app, "suite_home")
    click(app, "open_tube_load")
    click(app, "add_force")
    for key, value in {
        "tube_length": 305.625, "support_a": 100.625, "support_b_offset": 12.,
        "tube_od": 3.96875, "tube_id": 3.219, "tube_weight": 370.,
        "force_1_magnitude": 130.44, "force_1_position": 305.625,
    }.items():
        app.number_input(key=key).set_value(value)
    app.run()
    tube_metrics = metrics(app)
    assert "6,129.07" in tube_metrics[1][1]
    click(app, "suite_home")
    click(app, "open_coil_cg")
    click(app, "cg_load_example")
    assert app.metric[0].value == "1,466 lbf"

    click(app, "suite_home")
    click(app, "open_shipping_frame")
    assert metrics(app) == frame_metrics
    assert app.session_state.sf_solution_digest == frame_digest
    assert app.number_input(key="sf_mesh").value == 16
    click(app, "sf_reset_design")
    click(app, "suite_home")
    click(app, "open_tube_load")
    assert metrics(app) == tube_metrics


def test_frame_draft_and_displayed_units_survive_home_and_deleted_ids_stay_deleted():
    app = start()
    click(app, "open_shipping_frame")
    click(app, "sf_disclaimer_ok")
    click(app, "sf_add_beam")
    click(app, "sf_add_beam")
    click(app, "sf_add_rod")
    app.checkbox(key="sf_rod_T1_radius_mode").check().run()
    app.number_input(key="sf_rod_T1_radius").set_value(.375).run()
    app.number_input(key="sf_beam_B1_length").set_value(53.).run()
    click(app, "sf_add_coil")
    app.number_input(key="sf_coil_C1_x").set_value(8.5)
    click(app, "suite_home")
    click(app, "open_coil_cg")
    click(app, "suite_home")
    click(app, "open_shipping_frame")
    assert app.checkbox(key="sf_rod_T1_radius_mode").value
    assert app.number_input(key="sf_rod_T1_radius").value == .375
    assert app.session_state.sf_model["rods"][0]["diameter"] == .75
    assert app.number_input(key="sf_beam_B1_length").value == 53.
    assert app.number_input(key="sf_beam_B1_x").value is None
    assert app.number_input(key="sf_coil_C1_x").value == 8.5
    click(app, "sf_coil_C1_del")
    click(app, "sf_add_coil")
    assert app.number_input(key="sf_coil_C1_x").value is None


def test_another_session_gets_its_own_inputs():
    first = start()
    click(first, "open_tube_load")
    first.number_input(key="tube_length").set_value(222.).run()
    second = start()
    click(second, "open_tube_load")
    assert second.number_input(key="tube_length").value is None
    second.number_input(key="tube_length").set_value(333.).run()
    click(first, "suite_home")
    click(first, "open_tube_load")
    assert first.number_input(key="tube_length").value == 222.
