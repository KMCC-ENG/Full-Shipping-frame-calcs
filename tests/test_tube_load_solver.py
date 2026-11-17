"""Independent reference, limiting-case and critical-point tests."""
import csv
from dataclasses import replace
from decimal import Decimal, localcontext
from io import StringIO
from pathlib import Path
import sys
import unittest
from xml.etree import ElementTree

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from beam_stress_calculator import (Beam, Load, solve_beam, check_equilibrium,
                                   critical_points, peak, export_csv, tube_svg, section_svg)


def finite_element_reference(beam, loads):
    """Independent Hermite beam elements, with high precision for tiny cells."""
    with localcontext() as context:
        context.prec=50
        return _element_reference_decimal(beam,loads)


def _element_reference_decimal(beam,loads):
    nodes=sorted(set([0.,beam.length,beam.a,beam.b]+
                     [x for l in loads for x in (l.start,l.finish)]+
                     np.linspace(0,beam.length,7).tolist()))
    n=len(nodes)
    D=lambda x:Decimal(str(x))
    zero=Decimal(0)
    stiffness=[[zero for _ in range(2*n)] for _ in range(2*n)]
    force=[zero for _ in range(2*n)]
    elements=[]
    for i,(x0,x1) in enumerate(zip(nodes,nodes[1:])):
        h=D(x1)-D(x0)
        factor=D(beam.ei)/h**3
        k=[[factor*v for v in row] for row in
           [[12,6*h,-12,6*h],[6*h,4*h*h,-6*h,2*h*h],
            [-12,-6*h,12,-6*h],[6*h,2*h*h,-6*h,4*h*h]]]
        mid=(x0+x1)/2
        q=sum((D(l.force)/(D(l.finish)-D(l.start)) for l in loads
               if l.kind=="uniform" and l.start<mid<l.finish),zero)
        f=[q*v for v in [h/2,h*h/12,h/2,-h*h/12]]
        dofs=[2*i,2*i+1,2*i+2,2*i+3]
        for ii in range(4):
            force[dofs[ii]]+=f[ii]
            for jj in range(4):
                stiffness[dofs[ii]][dofs[jj]]+=k[ii][jj]
        elements.append((dofs,k,f))
    for load in loads:
        if load.kind=="point":
            force[2*nodes.index(load.start)]+=D(load.force)
    ai,bi=nodes.index(beam.a),nodes.index(beam.b)
    fixed=[2*ai,2*ai+1,2*bi,2*bi+1]
    free=sorted(set(range(2*n))-set(fixed))
    displacement=[zero for _ in range(2*n)]
    if free:
        augmented=[[stiffness[i][j] for j in free]+[force[i]] for i in free]
        count=len(free)
        for col in range(count):
            pivot=max(range(col,count),key=lambda row:abs(augmented[row][col]))
            augmented[col],augmented[pivot]=augmented[pivot],augmented[col]
            for row in range(col+1,count):
                ratio=augmented[row][col]/augmented[col][col]
                for j in range(col+1,count+1):
                    augmented[row][j]-=ratio*augmented[col][j]
                augmented[row][col]=zero
        values=[zero for _ in free]
        for row in range(count-1,-1,-1):
            values[row]=(augmented[row][-1]-sum((augmented[row][j]*values[j]
                         for j in range(row+1,count)),zero))/augmented[row][row]
        for i,v in zip(free,values):
            displacement[i]=v
    reactions=[sum((stiffness[i][j]*displacement[j] for j in range(2*n)),zero)-force[i] for i in fixed]
    ends=[[sum((k[i][j]*displacement[dofs[j]] for j in range(4)),zero)-f[i]
           for i in range(4)] for dofs,k,f in elements]
    return nodes,np.array([float(v) for v in displacement]),np.array([float(v) for v in reactions]),[np.array([float(v) for v in end]) for end in ends]


class BeamSolverTests(unittest.TestCase):
    def setUp(self):
        self.beam=Beam(305.625,100.625,293.625,3.96875,3.219,29e6)
        self.example=[Load("self-weight","uniform",-370,0,305.625),
                      Load("tip","point",-130.44,305.625)]

    def assertClose(self,a,b,atol=1e-8):
        np.testing.assert_allclose(a,b,rtol=2e-8,atol=atol)

    def test_worked_example_reactions_and_support_sides(self):
        s=solve_beam(self.beam,self.example)
        self.assertClose([s.ra,s.rb,s.ca,s.cb],
                         [238.646216768916,261.793783231084,-2371.16215064758,-2105.46301295160])
        self.assertClose([s.at(self.beam.a,"moment","left"),s.at(self.beam.a,"moment","right"),
                          s.at(self.beam.b,"moment","left"),s.at(self.beam.b,"moment","right")],
                         [-6129.07080777096,-3757.90865712338,-3757.90865712338,-1652.44564417178])
        self.assertTrue(all(r["Pass"] for r in check_equilibrium(s)))

    def test_fixed_fixed_full_uniform_closed_form(self):
        b=replace(self.beam,a=0,b=self.beam.length)
        W=370.
        q=W/b.length
        s=solve_beam(b,[Load("uniform","uniform",-W,0,b.length)])
        self.assertClose([s.ra,s.rb,s.ca,s.cb],
                         [W/2,W/2,q*b.length**2/12,-q*b.length**2/12])
        self.assertClose(s.at(b.length/2,"deflection"),-q*b.length**4/(384*b.ei))

    def test_asymmetric_fixed_fixed_point_closed_form(self):
        b=replace(self.beam,a=0,b=self.beam.length)
        P=123.4
        x=.37*b.length
        y=b.length-x
        s=solve_beam(b,[Load("point","point",-P,x)])
        self.assertClose([s.ra,s.rb,s.ca,s.cb],
                         [P*y*y*(3*x+y)/b.length**3,P*x*x*(x+3*y)/b.length**3,
                          P*x*y*y/b.length**2,-P*x*x*y/b.length**2])
        self.assertNotAlmostEqual(s.ra,s.rb)

    def test_load_on_each_support_is_carried_directly(self):
        for where in [self.beam.a,self.beam.b]:
            with self.subTest(where=where):
                s=solve_beam(self.beam,[Load("at clamp","point",-123.4,where)])
                expected=[123.4,0,0,0] if where==self.beam.a else [0,123.4,0,0]
                self.assertClose([s.ra,s.rb,s.ca,s.cb],expected)
                for quantity in ["moment","shear","deflection","stress"]:
                    self.assertLess(abs(peak(s,quantity).value),1e-8)
                    self.assertEqual(critical_points(s,quantity),[])

    def test_left_tip_cantilever_limit(self):
        P=81.
        s=solve_beam(self.beam,[Load("left tip","point",-P,0)])
        self.assertClose([s.ra,s.rb,s.ca,s.cb],[P,0,-P*self.beam.a,0])
        self.assertClose(s.at(0,"deflection"),-P*self.beam.a**3/(3*self.beam.ei))

    def test_right_tip_cantilever_limit(self):
        P=81.
        b=self.beam.length-self.beam.b
        s=solve_beam(self.beam,[Load("right tip","point",-P,self.beam.length)])
        self.assertClose([s.ra,s.rb,s.ca,s.cb],[0,P,0,P*b])
        self.assertClose(s.at(self.beam.length,"deflection"),-P*b**3/(3*self.beam.ei))

    def test_uniform_left_cantilever_limit(self):
        a=self.beam.a
        W=110.
        s=solve_beam(self.beam,[Load("left only","uniform",-W,0,a)])
        self.assertClose([s.ra,s.rb,s.ca,s.cb],[W,0,-W*a/2,0])
        self.assertClose(s.at(0,"deflection"),-W*a**3/(8*self.beam.ei))

    def test_outboard_tip_forces_against_cantilever_solutions(self):
        b = Beam(120, 20, 110, 4, 3, 29e6)
        offset = 6.
        for end, clamp, side, direction in [(0., b.a, "left", -1), (b.length, b.b, "right", 1)]:
            arm = abs(end - clamp)
            for force in (-100., 100.):
                with self.subTest(end=end, force=force):
                    cg = end + direction * offset
                    s = solve_beam(b, [Load("fitting", "point", force, cg)])
                    support_moment = -force * (cg - clamp)
                    reactions = ([-force, 0., support_moment, 0.] if side == "left"
                                 else [0., -force, 0., support_moment])
                    self.assertClose([s.ra, s.rb, s.ca, s.cb], reactions)
                    self.assertClose(s.at(end, "moment"), force * offset)
                    self.assertClose(s.at(clamp, "moment", side), force * (arm + offset))
                    self.assertClose(s.at(end, "deflection"),
                                     force * (arm**3 / 3 + offset * arm**2 / 2) / b.ei)
                    self.assertClose(s.at(end, "rotation"),
                                     direction * force * (arm**2 / 2 + offset * arm) / b.ei)
                    self.assertClose(peak(s, "stress").value, abs(force) * (arm + offset) / b.modulus)
                    self.assertClose([s.end_transfers[0].force, s.end_transfers[0].couple],
                                     [force, direction * offset * force])
                    self.assertTrue(all(row["Pass"] for row in check_equilibrium(s)))

    def test_external_loads_at_clamped_tube_ends(self):
        b = Beam(120, 0, 120, 4, 3, 29e6)
        s = solve_beam(b, [Load("left", "point", -100, -6), Load("right", "point", -80, 124)])
        self.assertClose([s.ra, s.rb, s.ca, s.cb], [100, 80, -600, 320])
        for quantity in ["moment", "shear", "deflection", "stress"]:
            self.assertClose(peak(s, quantity).value, 0.)

    def test_mixed_outboard_loads_against_explicit_extension_elements(self):
        # The independent reference actually meshes the full extensions.
        # Only its reactions and fields on the physical tube are compared.
        b = Beam(120, 20, 110, 4, 3, 29e6)
        loads = [Load("cross both", "uniform", -145, -10, 135),
                 Load("cross left", "uniform", 42, -12, 50),
                 Load("cross right", "uniform", -37, 89, 130),
                 Load("right only", "uniform", -20, 126, 138),
                 Load("left only", "uniform", 15, -9, -4),
                 Load("left fitting", "point", -55, -18),
                 Load("right fitting", "point", 17, 124), Load("tube", "point", -99, 67)]
        self.compare_reference(b, loads)
        s = solve_beam(b, loads)
        rows = list(csv.DictReader(StringIO(export_csv(s))))
        xs = [float(row["x_in"]) for row in rows]
        self.assertClose([min(xs), max(xs)], [0, b.length])
        self.assertEqual(len(s.end_transfers), 8)
        cross_both = [t for t in s.end_transfers if t.name == "cross both"]
        self.assertClose([[t.force, t.couple] for t in cross_both], [[-10, 50], [-15, -112.5]])

    def test_independent_elements_for_mixed_overlapping_loads(self):
        b=Beam(240,49,197,4.1,3.2,28e6)
        loads=[Load("part 1","uniform",-278,10,165),Load("part 2","uniform",119,80,220),
               Load("part 3","uniform",-97,180,240),Load("up point","point",67,33),
               Load("down point","point",-214,113),Load("at support","point",-43,197)]
        self.compare_reference(b,loads)

    def compare_reference(self,b,loads):
        s=solve_beam(b,loads)
        nodes,d,reactions,ends=finite_element_reference(b,loads)
        self.assertClose([s.ra,s.ca,s.rb,s.cb],reactions,atol=2e-5)
        for i,x in enumerate(nodes):
            if x < 0 or x > b.length:
                continue
            self.assertClose(s.at(x,"deflection"),d[2*i],atol=1e-8)
            self.assertClose(s.at(x,"rotation"),d[2*i+1],atol=1e-9)
        for i,(x0,x1) in enumerate(zip(nodes,nodes[1:])):
            if x0 < 0 or x1 > b.length:
                continue
            self.assertClose(s.at(x0,"moment","right"),-ends[i][1],atol=2e-5)
            self.assertClose(s.at(x1,"moment","left"),ends[i][3],atol=2e-5)
            self.assertClose(s.at(x0,"shear","right"),ends[i][0],atol=2e-6)
            self.assertClose(s.at(x1,"shear","left"),-ends[i][2],atol=2e-6)
        self.assertTrue(all(r["Pass"] for r in check_equilibrium(s)))

    def test_random_mixed_loads_against_independent_elements(self):
        rng=np.random.default_rng(410)
        for case in range(12):
            b=Beam(200,35,170,4,3,29e6)
            loads=[]
            for j in range(3):
                x=float(rng.uniform(0,b.length))
                loads.append(Load(str(j),"point",float(rng.uniform(-300,300)),x))
            for j in range(3):
                start,end=sorted(rng.uniform(0,b.length,2))
                loads.append(Load("U"+str(j),"uniform",float(rng.uniform(-300,300)),float(start),float(end)))
            with self.subTest(case=case):
                self.compare_reference(b,loads)

    def test_superposition_and_sign_reversal(self):
        s=solve_beam(self.beam,self.example)
        parts=[solve_beam(self.beam,[load]) for load in self.example]
        reverse=solve_beam(self.beam,[replace(l,force=-l.force) for l in self.example])
        for x in np.linspace(0,self.beam.length,25):
            for q in ["moment","shear","deflection","rotation"]:
                self.assertClose(s.at(x,q),sum(p.at(x,q) for p in parts))
                self.assertClose(s.at(x,q),-reverse.at(x,q))
            self.assertClose(s.at(x,"stress"),reverse.at(x,"stress"))

    def test_young_modulus_only_changes_deformation(self):
        s=solve_beam(self.beam,self.example)
        other=solve_beam(replace(self.beam,young=self.beam.young*2),self.example)
        self.assertClose([s.ra,s.rb,s.ca,s.cb],[other.ra,other.rb,other.ca,other.cb])
        for x in [0,150,220,305.625]:
            self.assertClose(s.at(x,"moment"),other.at(x,"moment"))
            self.assertClose(s.at(x,"deflection"),2*other.at(x,"deflection"))

    def test_zero_loads_and_exact_cancellation(self):
        for loads in [[],[Load("down","uniform",-100,20,230),Load("up","uniform",100,20,230)]]:
            s=solve_beam(self.beam,loads)
            for q in ["moment","shear","stress","deflection"]:
                self.assertLess(abs(peak(s,q).value),1e-10)
                self.assertEqual(critical_points(s,q),[])

    def test_critical_points_include_roots_and_one_sided_jumps(self):
        s=solve_beam(self.beam,self.example)
        p=peak(s,"moment")
        self.assertClose([p.x,p.value],[100.625,-6129.07080777])
        self.assertEqual(p.side,"left")
        stress_points=critical_points(s,"stress")
        zeros=[c.x for c in stress_points if 110<c.x<280 and abs(c.value)<1e-6]
        self.assertClose(zeros,[141.41069902,252.83930098],atol=1e-6)
        for c in critical_points(s,"deflection"):
            if "local minimum" in c.kinds and 0<c.x<self.beam.length:
                self.assertClose(s.at(c.x,"rotation"),0,atol=1e-10)
        jumps=[c for c in critical_points(s,"moment") if "jump" in c.kinds]
        self.assertEqual(len(jumps),4)
        end=[c for c in critical_points(s,"moment") if abs(c.x-self.beam.length)<1e-8]
        self.assertEqual(end[0].value,0.0)

    def test_csv_preserves_both_sides(self):
        s=solve_beam(self.beam,self.example)
        rows=list(csv.DictReader(StringIO(export_csv(s))))
        a=[r for r in rows if abs(float(r["x_in"])-self.beam.a)<1e-8]
        self.assertEqual({r["side"] for r in a},{"left","right"})
        self.assertEqual(len({round(float(r["moment_lbf_in"]),5) for r in a}),2)

    def test_schematic_has_no_initial_load_arrows_and_tracks_loads(self):
        empty=tube_svg(self.beam,[])
        self.assertIn("No applied loads",empty)
        self.assertNotIn('marker-end="url(#point-head)"',empty)
        live=tube_svg(self.beam,self.example)
        self.assertIn('marker-end="url(#point-head)"',live)
        self.assertIn('130.44 lbf',live)
        self.assertIn('3.96875',section_svg(self.beam))

    def test_outboard_schematic_uses_entered_coordinates_and_physical_tube_length(self):
        b = Beam(120, 20, 110, 4, 3, 29e6)
        svg = ElementTree.fromstring(tube_svg(b, [Load("left", "point", -50, -6),
                                                  Load("right", "point", -100, 132)]))
        lines = svg.findall("{http://www.w3.org/2000/svg}line")
        tube = next(line for line in lines if line.get("stroke-width") == "8")
        xmin, xmax = float(tube.get("x1")), float(tube.get("x2"))
        xs = [float(line.get("x1")) for line in lines if line.get("marker-end") == "url(#point-head)"]
        self.assertClose([(x - xmin) / (xmax - xmin) * b.length for x in xs], [-6, 132], atol=1e-5)
        self.assertEqual(len([line for line in lines if line.get("stroke-dasharray")]), 2)

    def test_invalid_inputs(self):
        bad=[(replace(self.beam,id=5),[]),(replace(self.beam,a=300),[]),
             (self.beam,[Load("nonfinite","point",1,float("inf"))]),
             (self.beam,[Load("missing end","uniform",1,20)]),
             (self.beam,[Load("zero length","uniform",1,20,20)]),
             (self.beam,[Load("bad","uniform",1,30,20)])]
        for b,loads in bad:
            with self.subTest(loads=loads):
                with self.assertRaises(ValueError):
                    solve_beam(b,loads)


if __name__=="__main__":
    unittest.main()
