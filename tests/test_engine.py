from pathlib import Path
import sys,copy,math
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from frame_engine import solve_frame,element_flexibility
from frame_geometry import Section,ModelError,section_properties
from frame_models import base_model,new_beam,new_pin,component,set_section_type,two_layer_example,block_example,four_layer_example,load_model,model_json

def reference_model(uniform=False,position=24.):
 m=base_model();b=new_beam(1);b['section_type']='Custom properties';b['auto_cut']=False;b['manual']={'A':3.,'I':2.,'ctop':1.5,'cbottom':1.5,'As':2.5,'width':1.}
 t=copy.deepcopy(b);t.update(id='B2',name='Unloaded member',y=50.)
 m['beams']=[b,t];m['coils']=[];m['rods']=[];m['blocks']=[]
 m['pins']=[new_pin(1),new_pin(2)];m['pins'][0]['x']=0;m['pins'][1]['x']=48
 m['loading'].update(coil_weight=0.,self_weight=False,frames=1);m['analysis']['elements']=8
 m['loads']=[{'id':'F1','name':'Reference load','kind':'Uniform' if uniform else 'Point','beam':'B1','x':0. if uniform else position,'end':48.,'value':-1000.}]
 return m

def test_uniform_element_matches_timoshenko_matrix():
 L=4.;E=29e6;G=E/2.6;I=2.;As=1.
 s=Section(3,0,0,I,1,0,-1,1,-1,1,As)
 root,w=np.polynomial.legendre.leggauss(4);pp=[(ww*L/2,(1+x)*L/2,s) for x,ww in zip(root,w)]
 K,f,_,_=element_flexibility(L,E,G,pp,True,-12.)
 phi=12*E*I/(G*As*L**2)
 ref=E*I/(L**3*(1+phi))*np.array([[12,6*L,-12,6*L],[6*L,(4+phi)*L**2,-6*L,(2-phi)*L**2],[-12,-6*L,12,-6*L],[6*L,(2-phi)*L**2,-6*L,(4+phi)*L**2]])
 assert np.allclose(K,ref,rtol=1e-11,atol=1e-7)
 assert f==pytest.approx(-12*np.array([L/2,L**2/12,L/2,-L**2/12]))

@pytest.mark.parametrize('uniform',[False,True])
def test_simply_supported_closed_form(uniform):
 m=reference_model(uniform);z=solve_frame(m,refine_peaks=False);r=z.beam_results['B1'];L=48.;P=1000.;E=29e6;I=2.;As=2.5;G=E/2.6
 exact=(5*P*L**3/(384*E*I)+P*L/(8*G*As)) if uniform else P*L**3/(48*E*I)+P*L/(4*G*As)
 moment=P*L/8 if uniform else P*L/4
 assert abs(r['peak_deflection']['v'])==pytest.approx(exact,rel=2e-5)
 assert abs(r['peak_moment']['M'])==pytest.approx(moment,rel=2e-6)
 assert [p['force'] for p in z.reactions]==pytest.approx([500,500],rel=2e-6)
 assert z.checks['max_recovery_mismatch']<1e-10

def test_asymmetric_reactions_and_equal_validation():
 m=reference_model(False,12.);z=solve_frame(m,refine_peaks=False)
 assert [p['force'] for p in z.reactions]==pytest.approx([750,250],rel=2e-6)
 m['loading']['equal_reactions']=True
 with pytest.raises(ModelError,match='unbalanced'):solve_frame(m)
 m=reference_model();m['loading']['equal_reactions']=True;z=solve_frame(m,refine_peaks=False)
 assert [p['force'] for p in z.reactions]==pytest.approx([500,500],rel=1e-10)

def test_single_layer_closed_form_and_empty_model_rejection():
 m=reference_model();m['beams']=m['beams'][:1]
 assert load_model(model_json(m))==m
 z=solve_frame(m,refine_peaks=False)
 assert [p['force'] for p in z.reactions]==pytest.approx([500.,500.],abs=.001)
 assert abs(z.beam_results['B1']['peak_moment']['M'])==pytest.approx(12000.,rel=2e-6)
 m['beams']=[]
 assert load_model(model_json(m))==m
 with pytest.raises(ModelError,match='at least one beam layer'):solve_frame(m)

def test_seven_layer_stack_transfers_all_weight_to_lifting_beam():
 m=base_model();m['analysis']['elements']=8;m['loading'].update(self_weight=True,frames=1)
 for i in range(1,8):
  b=new_beam(i);b.update(y=float(i-1),section_type='Section + flat bar',auto_cut=False)
  b['components']=[component('Flat bar',h=1.,w=2.,t=1.)];m['beams'].append(b)
 m['pins']=[new_pin(1),new_pin(2)];m['pins'][0]['x']=0.;m['pins'][1]['x']=48.
 assert load_model(model_json(m))==m
 z=solve_frame(m,refine_peaks=False);weight=7*48.*2.*m['materials']['frame']['density']
 assert len(z.beam_results)==7
 assert [p['force'] for p in z.reactions]==pytest.approx([weight/2,weight/2],abs=.001)
 for i in range(2,8):
  contacts=[q for q in z.forces if q['kind']=='beam_contact' and q['lower']==f'B{i-1}' and q['upper']==f'B{i}']
  assert sum(q['force'] for q in contacts)==pytest.approx((8-i)*48.*2.*m['materials']['frame']['density'],abs=.001)
 assert abs(z.checks['vertical_residual'])<.001

def test_physical_rod_stiffness_and_contact_complementarity():
 m=two_layer_example();m['analysis']['elements']=24;z=solve_frame(m,refine_peaks=False)
 for r in z.rods:
  assert r['At']==pytest.approx(math.pi/4*(r['diameter']-.9743/r['tpi'])**2)
  assert r['k']==pytest.approx(m['materials']['rod']['E']*r['At']/r['effective_length'])
  assert r['tension']>=0
  link=next(q for q in z.forces if q['kind']=='rod' and q['label']==r['id'])
  assert r['tension']==pytest.approx(r['k']*max(-link['gap'],0),abs=.02)
 for q in z.forces:
  if q['kind']!='rod':
   assert q['gap']>=-1e-5 and q['force']>=0
   assert abs(q['force']*q['gap'])<.01
 assert abs(z.checks['vertical_residual'])<.01
 for b in z.checks['beam_equilibrium']:
  assert abs(b['force_residual'])<.01 and abs(b['moment_residual'])<.05

def test_rectangular_blocks_create_upper_contacts():
 # Make the lower member relatively stiff and press on the two smaller coils.
 # A tangent block is not guaranteed to stay loaded in every frame: the normal
 # block example deliberately permits open seats under its lifting deformation.
 m=block_example();m['analysis']['elements']=24;m['rods']=[]
 m['beams'][0]['components']=[component('Flat bar',h=2.,w=100.,t=1.)]
 m['loading'].update(coil_weight=0.,self_weight=False)
 m['loads']=[{'id':f'F{i}','name':'Pad contact test','beam':'B2','kind':'Point','x':x,'value':-1000.} for i,x in enumerate([16.,32.],1)]
 pad=solve_frame(m,refine_peaks=False)
 m['blocks']=[];no=solve_frame(m,refine_peaks=False)
 for cid in ['C2','C4']:
  a=next(q for q in pad.forces if q.get('coil')==cid and q['kind']=='coil_upper')
  b=next(q for q in no.forces if q.get('coil')==cid and q['kind']=='coil_upper')
  assert a['force']>1 and b['force']<.01
 assert len(pad.model['beams'])==2
 assert sum(w['weight'] for w in pad.weights)>sum(w['weight'] for w in no.weights)

def test_cut_section_and_mesh_refinement():
 m=two_layer_example();m['analysis']['elements']=24;cut=solve_frame(m,refine_peaks=False)
 for bid in ['B1','B2']:
  assert cut.geometry.props(bid,8.).I<section_properties(cut.geometry.section(bid,8.,cut=False)).I
 fine=solve_frame(m,48,refine_peaks=False)
 for bid in cut.beam_results:
  a=cut.beam_results[bid]['peak_stress']['stress'];b=fine.beam_results[bid]['peak_stress']['stress']
  assert abs(a-b)/b<.025

def test_four_and_five_layer_connectivity():
 m=four_layer_example();m['analysis']['elements']=24;z=solve_frame(m,refine_peaks=False)
 assert len(z.beam_results)==4 and abs(z.checks['vertical_residual'])<.02
 b=new_beam(5);b.update(y=16.,x=3.,length=41.);m['beams'].append(b)
 z=solve_frame(m,refine_peaks=False)
 assert len(z.beam_results)==5 and z.checks['stabilizer_max_force']<.001
 assert any(q['kind']=='beam_contact' and q.get('upper')=='B5' and q['force']>0 for q in z.forces)
 assert len(z.weights)==5 and all(w['included'] for w in z.weights)

def test_three_layers_with_welded_middle_components():
 m=four_layer_example();m['analysis']['elements']=24
 b=m['beams'][1];set_section_type(b,'Angle + HSS');b['components'][1]['h']=3.5625
 m['beams']=[q for q in m['beams'] if q['id']!='B3']
 for r in m['rods']:
  for endpoint in ['weld','nut']:
   if r[endpoint]=='B3':r[endpoint]='B2'
 z=solve_frame(m,refine_peaks=False)
 assert len(z.beam_results)==3 and abs(z.checks['vertical_residual'])<.02
 assert len(z.geometry.beams['B2']['components'])==2

def test_rod_collision_is_rejected():
 m=two_layer_example();m['rods'][0]['x']=8.
 with pytest.raises(ModelError,match='intersects'):solve_frame(m)

def test_lifting_chains_cannot_supply_downward_reactions():
 m=reference_model(False,6.);m['pins'][0]['x']=12.;m['pins'][1]['x']=36.
 with pytest.raises(ModelError,match='downward reaction'):solve_frame(m)


def angle_model():
 m=base_model();b=new_beam(1);b['auto_cut']=False;m['beams']=[b]
 m['pins']=[new_pin(1),new_pin(2)];m['pins'][0]['x']=0.;m['pins'][1]['x']=48.
 m['loads']=[{'id':'F1','name':'Center load','kind':'Point','beam':'B1','x':24.,'value':-1000.}]
 m['analysis'].update(elements=24,timoshenko=False,coupled_bending=True)
 return m


def test_free_angle_matches_independent_unsymmetrical_bending():
 m=angle_model();s=solve_frame(m);r=s.beam_results['B1']
 # Summing the two leg rectangles, independently of the app geometry routines.
 A=3*.375+.375*2.625
 centroid=(3*.375*.1875+.375*2.625*1.6875)/A
 I=3*.375**3/12+3*.375*(.1875-centroid)**2+.375*2.625**3/12+.375*2.625*(1.6875-centroid)**2
 product=3*.375*(1.5-centroid)*(.1875-centroid)+.375*2.625*(.1875-centroid)*(1.6875-centroid)
 effective=I-product**2/I
 exact=1000*48**3/(48*29e6*effective)
 stresses=[12000*(product*(z-centroid)-I*(y-centroid))/(I*I-product**2) for z,y in [(0,0),(3,0),(3,.375),(.375,.375),(.375,3),(0,3)]]
 assert abs(r['peak_deflection']['v'])==pytest.approx(exact,rel=2e-6)
 assert r['peak_stress']['stress']==pytest.approx(max(map(abs,stresses)),rel=2e-6)
 assert abs(r['peak_lateral_deflection']['w'])==pytest.approx(abs(product/I)*exact,rel=2e-6)
 assert [p['force'] for p in s.reactions]==pytest.approx([500,500],abs=.001)
 assert s.checks['max_recovery_mismatch']<1e-9


def test_lateral_braces_restore_planar_curvature_for_central_point_load():
 m=angle_model();m['analysis'].update(free_lateral=False,lateral_constraints=[
  {'id':f'L{i}','beam':'B1','x':x,'kind':'Displacement'} for i,x in enumerate([0.,24.,48.],1)])
 s=solve_frame(m);r=s.beam_results['B1'];I=1.75968017578125
 assert abs(r['peak_deflection']['v'])==pytest.approx(1000*48**3/(48*29e6*I),rel=2e-6)
 assert max(abs(p['w']) for p in r['samples'])<1e-8
 assert r['peak_stress']['stress']==pytest.approx(12000*2.1125/I,rel=2e-6)
 assert len(s.lateral_reactions)==3
 assert abs(sum(p['reaction'] for p in s.lateral_reactions))<.001
 assert abs(sum(p['reaction']*p['x'] for p in s.lateral_reactions))<.01
 assert max(abs(p['reaction']) for p in s.lateral_reactions)>100


def test_rotational_lateral_clamp_and_missing_restraints():
 m=angle_model();m['analysis'].update(free_lateral=False,lateral_constraints=[])
 with pytest.raises(ModelError,match='Add a lateral constraint'):solve_frame(m)
 m['analysis']['lateral_constraints']=[{'id':'L1','beam':'B1','x':12.,'kind':'Displacement and rotation'}]
 s=solve_frame(m);n=s.beam_nodes['B1'];i=int(np.argmin(abs(n['x']-12.)))
 assert abs(s.u[n['dofs'][i,2]])<1e-10 and abs(s.u[n['dofs'][i,3]])<1e-10
 assert len(s.lateral_reactions)==2
 m['analysis']['lateral_constraints'][0]['x']=49.
 with pytest.raises(ModelError,match='outside its beam'):solve_frame(m)


@pytest.mark.parametrize('shear',[False,True])
def test_coupled_symmetric_rectangle_preserves_original_response(shear):
 m=reference_model(True);m['beams']=m['beams'][:1]
 m['analysis']['timoshenko']=shear
 original=solve_frame(m);p=m['beams'][0]['manual']
 p.update(Iyy=.25,Izy=0.,cleft=.5,cright=.5,Asz=2.5)
 m['analysis']['coupled_bending']=True;coupled=solve_frame(m)
 for key,field in [('peak_deflection','v'),('peak_moment','M'),('peak_stress','stress')]:
  assert coupled.beam_results['B1'][key][field]==pytest.approx(original.beam_results['B1'][key][field],rel=2e-6)
 assert abs(coupled.beam_results['B1']['peak_lateral_deflection']['w'])<1e-10


def test_nested_channel_bar_transmits_independent_center_point_load():
 m=base_model();m['analysis'].update(timoshenko=False,elements=24)
 lo=new_beam();lo.update(section_type='Custom draw',auto_cut=False)
 lo['components']=[component('Custom draw',drawing=[{'type':'polygon','points':[[0,0],[4,0],[4,2],[3.5,2],[3.5,.5],[.5,.5],[.5,2],[0,2]]}])]
 up=new_beam(2);up.update(section_type='Custom draw',y=.5,auto_cut=False)
 up['components']=[component('Custom draw',drawing=[{'type':'rectangle','x':0.,'y':0.,'w':2.,'h':1.}])];up['components'][0]['dz']=1.
 m['beams']=[lo,up]
 for bid in ['B1','B2']:
  for x in [0.,48.]:
   p=new_pin(len(m['pins'])+1);p.update(beam=bid,x=x);m['pins'].append(p)
 m['loads']=[{'id':'F1','name':'Bearing test','kind':'Point','beam':'B2','x':24.,'value':-480.}]
 s=solve_frame(m)
 Il=1.180059523809524;Iu=1/6;transfer=480*Il/(Il+Iu)
 center=sum(q['force'] for q in s.forces if q['kind']=='beam_contact' and abs(q['x']-24.)<1e-8)
 assert center==pytest.approx(transfer,rel=2e-5)
 for bid,I in [('B1',Il),('B2',Iu)]:
  r=s.beam_results[bid]
  assert abs(r['peak_deflection']['v'])==pytest.approx(480*48**3/(48*29e6*(Il+Iu)),rel=2e-5)
  assert r['peak_moment']['M']==pytest.approx(480*I/(Il+Iu)*48/4,rel=2e-5)


@pytest.mark.parametrize('shear',[False,True])
def test_disconnected_beam_rejected_in_both_shear_modes(shear):
 m=base_model();b=new_beam();b.update(section_type='Custom draw',auto_cut=False)
 b['components']=[component('Custom draw',drawing=[{'type':'rectangle','x':0,'y':0,'w':2,'h':1}, {'type':'rectangle','x':0,'y':3,'w':2,'h':1}])]
 m['beams']=[b];m['pins']=[new_pin(1),new_pin(2)];m['pins'][0]['x']=0.;m['pins'][1]['x']=48.
 m['loading']['self_weight']=True;m['analysis']['timoshenko']=shear
 with pytest.raises(ModelError,match='disconnected'):solve_frame(m)


@pytest.mark.parametrize('degrees',[13.,37.,64.,90.])
def test_rotated_rectangle_matches_principal_axis_solution(degrees):
 angle=math.radians(degrees);co,si=math.cos(angle),math.sin(angle)
 m=angle_model();b=m['beams'][0];b['section_type']='Custom draw'
 b['components']=[component('Custom draw',drawing=[{'type':'polygon','points':[[z*co-y*si,z*si+y*co] for z,y in [(-1.,-1.5),(1.,-1.5),(1.,1.5),(-1.,1.5)]]}])]
 Iz=4.5*co**2+2.*si**2;Iy=2.*co**2+4.5*si**2;Iyz=(2.-4.5)*co*si
 expected=1000*48**3/(48*29e6)*(Iy/(Iz*Iy-Iyz**2))
 s=solve_frame(m);r=s.beam_results['B1']
 assert abs(r['peak_deflection']['v'])==pytest.approx(expected,rel=2e-6)
 sigma=[]
 for z0,y0 in [(-1.,-1.5),(1.,-1.5),(1.,1.5),(-1.,1.5)]:
  z=z0*co-y0*si;y=z0*si+y0*co
  sigma.append(12000*(Iyz*z-Iy*y)/(Iz*Iy-Iyz**2))
 assert r['peak_stress']['stress']==pytest.approx(max(map(abs,sigma)),rel=2e-6)
