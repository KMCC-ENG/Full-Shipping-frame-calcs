from pathlib import Path
import sys,math
import pytest
from shapely.geometry import box
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from frame_geometry import Geometry,ModelError,section_properties,component_profile,drawing_geometry,shape_polygon,vertical_bearing_gap
from frame_models import base_model,new_beam,component

def test_identical_sections_reuse_shear_work_without_stale_geometry(monkeypatch):
 import frame_geometry as fg
 calls=[];original=fg.effective_shear_area
 def tracked(g,s):calls.append(g);return original(g,s)
 monkeypatch.setattr(fg,'effective_shear_area',tracked)
 fg.section_properties.cache_clear()
 m=base_model();b=new_beam();b['section_type']='HSS';b['components']=[component('HSS',4,4,.25)];m['beams']=[b]
 g=Geometry(m);first=g.props('B1',5.,True);other=g.props('B1',15.,True)
 assert first==other and len(calls)==1
 again=Geometry(m).props('B1',25.,True);assert again==first and len(calls)==1
 b['components'][0]['t']=.5
 changed=Geometry(m).props('B1',5.,True)
 assert changed.A>first.A and changed.I>first.I and len(calls)==2
 fg.section_properties.cache_clear()

def test_rectangle_centroid_inertia_shear_and_far_datum():
 s=section_properties(box(5,11,8,15),True)
 assert s.A==pytest.approx(12)
 assert s.yc==pytest.approx(13)
 assert s.I==pytest.approx(3*4**3/12)
 assert s.As==pytest.approx(5/6*12,rel=1e-10)
 q=section_properties(box(1e6,1e6,1e6+3,1e6+4))
 assert q.I==pytest.approx(s.I,rel=1e-10)

def test_angle_hss_channel_geometry():
 for spec,A in [(component('Angle',3,3,.375),2.109375),(component('HSS',4,4,.25),16-3.5**2),(component('C-channel',4,3,.25),2*3*.25+3.5*.25)]:
  s=section_properties(component_profile(spec),True)
  assert s.A==pytest.approx(A)
  assert 0<s.As<s.A
 hss=section_properties(component_profile(component('HSS',4,4,.25)))
 assert hss.I==pytest.approx((4**4-3.5**4)/12)
 angle=section_properties(component_profile(component('Angle',3,3,.375)))
 assert angle.I==pytest.approx(1.75968017578125)
 assert angle.yc==pytest.approx(.8875)

def test_drawn_circles_arcs_voids_and_invalid_outline():
 shapes=[{'type':'circle','x':0,'y':0,'r':2,'op':'add'},{'type':'circle','x':0,'y':0,'r':1,'op':'subtract'}]
 s=section_properties(drawing_geometry(shapes,512))
 assert s.A==pytest.approx(math.pi*3,rel=3e-5)
 assert s.I==pytest.approx(math.pi*(2**4-1)/4,rel=6e-5)
 arc={'type':'arc','x':0,'y':0,'r':2,'a0':0,'a1':180,'close':'segment'}
 s=section_properties(shape_polygon(arc,512))
 assert s.A==pytest.approx(2*math.pi,rel=3e-5)
 assert s.yc==pytest.approx(8/(3*math.pi),rel=3e-5)
 with pytest.raises(ModelError):drawing_geometry([{'type':'polygon','points':[[0,0],[2,2],[0,2],[2,0]]}])

def test_coil_removes_actual_section_material():
 m=base_model();b=new_beam();b.update(length=10);b['components']=[component('Flat bar',3,1,.1)];m['beams']=[b]
 m['coils']=[{'id':'C1','name':'Coil','x':5.,'y':3.,'r':1.}]
 g=Geometry(m);s=g.props('B1',5,shear=True);side=g.props('B1',3)
 assert s.A==pytest.approx(2)
 assert s.I==pytest.approx(2**3/12)
 assert s.yc==pytest.approx(1)
 assert side.A==pytest.approx(3)
 q=g.props('B1',5.6)
 assert q.A==pytest.approx(2.2)
 assert q.I==pytest.approx(2.2**3/12)
 assert s.As==pytest.approx(5/6*2,rel=1e-8)

def test_partial_length_welded_parallel_axis():
 m=base_model();b=new_beam();b['length']=20
 bottom=component('Flat bar',1,3,.1);top=component('Flat bar',1,1,.1);top.update(dy=1,start=5,length=10)
 b['components']=[bottom,top];m['beams']=[b]
 g=Geometry(m);plain=g.props('B1',2);combined=g.props('B1',8)
 yc=(3*.5+1*1.5)/4
 exact=3/12+3*(.5-yc)**2+1/12+(1.5-yc)**2
 assert plain.I==pytest.approx(3/12)
 assert combined.I==pytest.approx(exact)
 assert {5,15}.issubset(set(g.critical_x()))

def test_invalid_or_disconnected_section_rejected():
 with pytest.raises(ModelError):section_properties(box(0,0,0,0))
 with pytest.raises(ModelError):section_properties(box(0,0,2,1).union(box(0,2,2,3)),True)

def test_bearing_requires_material_at_the_same_depth():
 lower=component_profile(component('Angle',h=3.,w=3.,t=.375,flip_z=True))
 narrow=box(0,3,1,4)
 assert vertical_bearing_gap(lower,narrow)==pytest.approx(3-.375)
 wide=box(0,3,3,4)
 assert vertical_bearing_gap(lower,wide)==pytest.approx(0.)
 assert vertical_bearing_gap(lower,box(4,3,5,4)) is None


def test_bearing_finds_floor_and_ceiling_of_nested_closed_section():
 lower=box(0,0,4,4).difference(box(.5,.5,3.5,3.5))
 inside=box(1,.5,3,1.5)
 assert vertical_bearing_gap(lower,inside)==pytest.approx(0.)
 assert vertical_bearing_gap(inside,lower)==pytest.approx(2.)
 assert vertical_bearing_gap(lower,box(4,0,5,1)) is None


@pytest.mark.parametrize('shear',[False,True])
def test_disconnected_geometry_guard_is_independent_of_shear(shear):
 g=box(0,0,2,1).union(box(0,3,2,4))
 with pytest.raises(ModelError,match='disconnected'):section_properties(g,shear)
 # Subtraction arithmetic may legitimately consist of several removed regions.
 assert section_properties(g,allow_sliver=True).A==pytest.approx(4.)
