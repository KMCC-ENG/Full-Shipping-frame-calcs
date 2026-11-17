"""Interaction regressions for draft inputs, imports, analysis modes and results."""
from pathlib import Path
from io import BytesIO
import copy,sys
import pytest
from streamlit.testing.v1 import AppTest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from frame_models import base_model,default_model,new_beam,two_layer_example,model_json,load_model,reset_tab
from frame_geometry import ModelError

APP=Path(__file__).resolve().parents[1]/'shipping_frame_calculator.py'


def started(model=None):
 a=AppTest.from_file(str(APP),default_timeout=90)
 if model is not None:a.session_state.sf_model=copy.deepcopy(model)
 a.run();assert not a.exception
 return a


def test_frame_opens_directly_with_empty_model():
 a=AppTest.from_file(str(APP),default_timeout=90).run()
 assert a.title[0].value=='Shipping Frame Load Analyzer'
 assert not any(b.label=='OK' for b in a.button)
 assert a.session_state.sf_model['beams']==[]
 assert all(not a.session_state.sf_model[k] for k in ['coils','rods','pins','blocks'])
 assert not a.metric and not a.exception
 a.run();assert not any(b.label=='OK' for b in a.button)


def test_blank_beams_coils_rods_and_valid_zero_positions():
 a=started();a.button(key='sf_add_beam').click().run()
 assert a.selectbox(key='sf_beam_B1_type').value is None
 for key in ['x','y','length']:assert a.number_input(key='sf_beam_B1_'+key).value is None
 a.selectbox(key='sf_beam_B1_type').select('Angle').run()
 for key in ['h','w','t']:assert a.number_input(key='sf_beam_B1_Angle_0_'+key).value is None
 a.number_input(key='sf_beam_B1_x').set_value(0.).run()
 a.number_input(key='sf_beam_B1_y').set_value(0.).run()
 a.number_input(key='sf_beam_B1_length').set_value(48.).run()
 for key,val in [('h',3.),('w',3.),('t',.375)]:a.number_input(key='sf_beam_B1_Angle_0_'+key).set_value(val).run()
 assert a.selectbox(key='sf_beam_B1_Angle_0_rot').value is None
 a.selectbox(key='sf_beam_B1_Angle_0_rot').select(0).run()
 assert a.session_state.sf_model['beams'][0]['x']==0.
 a.button(key='sf_add_coil').click().run()
 for key in ['x','y','r']:assert a.number_input(key='sf_coil_C1_'+key).value is None
 a.button(key='sf_add_beam').click().run();a.button(key='sf_add_rod').click().run()
 for key in ['x','d','tpi']:assert a.number_input(key='sf_rod_T1_'+key).value is None
 assert a.selectbox(key='sf_rod_T1_weld').value is None
 assert a.selectbox(key='sf_rod_T1_nut').value is None
 assert not a.exception and not a.metric
 assert load_model(model_json(a.session_state.sf_model))==a.session_state.sf_model


def test_loaded_values_survive_unrelated_edits_and_tab_changes():
 m=two_layer_example();m['beams'][0].update(x=-2.25,length=61.125,y=-.875)
 m['beams'][0]['components'][0].update(h=3.625,w=4.25,t=.4375)
 m['materials']['frame']['E']=30.25e6
 a=started(m);before=copy.deepcopy(a.session_state.sf_model)
 a.number_input(key='sf_load_factor').set_value(1.375).run()
 after=a.session_state.sf_model
 for key in ['beams','coils','rods','pins','blocks','materials']:assert after[key]==before[key]
 a.number_input(key='sf_beam_B1_length').set_value(62.375).run()
 expected=copy.deepcopy(before['beams']);expected[0]['length']=62.375
 assert a.session_state.sf_model['beams']==expected
 a.number_input(key='sf_mesh').set_value(80).run()
 assert a.session_state.sf_model['beams']==expected
 assert a.session_state.sf_model['loading']['factor']==1.375
 assert not a.exception


def test_import_callback_replaces_stale_widgets_transactionally(monkeypatch):
 import streamlit as st
 file={'value':None}
 def uploader(label,**kwargs):
  st.session_state[kwargs['key']]=file['value']
 monkeypatch.setattr(st,'file_uploader',uploader)
 a=started(two_layer_example())
 a.number_input(key='sf_beam_B1_length').set_value(75.25).run()
 m=two_layer_example();m['beams'][0].update(length=66.375,y=-2.)
 m['beams'][0]['components'][0]['t']=.5
 file['value']=BytesIO(model_json(m).encode());a.run()
 a.button(key='sf_import_model').click().run()
 assert not a.exception and not a.error
 assert a.number_input(key='sf_beam_B1_length').value==66.375
 imported=copy.deepcopy(a.session_state.sf_model['beams'])
 a.number_input(key='sf_load_factor').set_value(1.5).run()
 assert a.session_state.sf_model['beams']==imported
 assert a.session_state.sf_model['beams'][0]['y']==-2.
 assert a.number_input(key='sf_beam_B1_Angle_0_t').value==.5


def test_new_tabs_and_moved_controls():
 a=started()
 assert [q.label for q in a.sidebar.tabs]==['Design','Loading','Material','Analysis']
 loading=a.sidebar.tabs[1];material=a.sidebar.tabs[2];analysis=a.sidebar.tabs[3]
 assert any(q.key=='sf_add_load' for q in loading.button)
 assert all(q.label!='Additional beam loads' for q in loading.expander)
 assert all(q.label!='Analysis settings' for q in loading.expander)
 assert any(q.label=='Optional nominal-stress comparison' for q in material.expander)
 assert any(q.key=='sf_mesh' for q in analysis.number_input)
 assert any('progressively finer' in q.value for q in analysis.info)
 assert any(q.label=='Load multiplier guide' for q in loading.expander)


def test_two_stage_coupling_and_constraint_inputs_round_trip():
 a=started(two_layer_example())
 assert not any(q.key=='sf_free_lateral' for q in a.checkbox)
 a.checkbox(key='sf_coupled_bending').check().run()
 assert a.checkbox(key='sf_free_lateral').value
 assert not any(q.key=='sf_lateral_add' for q in a.button)
 a.checkbox(key='sf_free_lateral').uncheck().run()
 a.button(key='sf_lateral_add').click().run()
 assert a.selectbox(key='sf_constraint_L1_beam').value is None
 assert a.number_input(key='sf_constraint_L1_x').value is None
 a.selectbox(key='sf_constraint_L1_beam').select('B1').run()
 a.number_input(key='sf_constraint_L1_x').set_value(0.).run()
 a.selectbox(key='sf_constraint_L1_kind').select('Displacement and rotation').run()
 a.checkbox(key='sf_free_lateral').check().run()
 a.checkbox(key='sf_free_lateral').uncheck().run()
 assert a.number_input(key='sf_constraint_L1_x').value==0.
 assert a.session_state.sf_model['analysis']['lateral_constraints']==[{'id':'L1','beam':'B1','x':0.,'kind':'Displacement and rotation'}]
 assert load_model(model_json(a.session_state.sf_model))==a.session_state.sf_model
 assert not a.exception


def test_independent_tab_resets_and_remove_last_layer():
 m=two_layer_example();m['analysis']['elements']=32;m['loading'].update(factor=1.4,allowable_beam=15000.)
 a=started(m);before=copy.deepcopy(a.session_state.sf_model)
 a.button(key='sf_reset_loading').click().run()
 assert a.session_state.sf_model['analysis']==before['analysis']
 assert a.session_state.sf_model['loading']['allowable_beam']==15000.
 a.button(key='sf_reset_analysis').click().run()
 assert a.session_state.sf_model['analysis']==default_model()['analysis']
 a.button(key='sf_reset_design').click().run()
 assert not a.session_state.sf_model['beams']
 a.button(key='sf_add_beam').click().run()
 assert not a.button(key='sf_beam_B1_remove').disabled
 a.button(key='sf_beam_B1_remove').click().run()
 assert not a.session_state.sf_model['beams'] and not a.exception


def test_calculations_and_directional_result_charts():
 a=started(two_layer_example());a.number_input(key='sf_mesh').set_value(16).run()
 a.checkbox(key='sf_coupled_bending').check().run()
 a.button(key='sf_calculate').click().run(timeout=90)
 assert not a.exception and not a.error and len(a.metric)==4
 a.radio(key='sf_direction_M').set_value('Lateral').run()
 assert not a.exception
 a.session_state.sf_result_tab='Calculations';a.run(timeout=90)
 assert len(a.latex)>40 and not a.exception
 assert any('I_{yz}' in q.value for q in a.latex)
 before=copy.deepcopy(a.session_state.sf_model['beams'])
 a.number_input(key='sf_load_factor').set_value(1.25).run()
 assert not a.metric and a.session_state.sf_model['beams']==before


def test_editor_blank_close_and_dimension_steps():
 a=started();a.button(key='sf_add_beam').click().run()
 a.selectbox(key='sf_beam_B1_type').select('Custom draw').run()
 a.button(key='sf_beam_B1_open_sketcher').click().run()
 assert a.session_state.sf_editor_open
 assert a.session_state.sf_model['beams'][0]['components'][0]['drawing']==[]
 assert a.number_input(key='sf_beam_B1_length').step==.5
 assert not a.exception


def test_model_and_draft_round_trips_and_duplicate_rejection():
 for m in [default_model(),two_layer_example()]:assert load_model(model_json(m))==m
 m=default_model();m['beams']=[new_beam(blank=True)]
 assert load_model(model_json(m))==m
 m=two_layer_example();m['coils'][1]['id']=m['coils'][0]['id']
 with pytest.raises(ModelError,match='unique'):load_model(model_json(m))
