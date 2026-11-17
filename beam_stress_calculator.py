"""Tube Load Analyzer — Streamlit app and exact piecewise beam solver.

Run: python -m streamlit run beam_stress_calculator.py
Units: inches, lbf, psi. Two ideal fixed supports; straight, uniform section.
Signed forces and deflection are positive upward; external couples are CCW
positive; internal bending moment is sagging positive. Stress is |M| / Z.
The analysis engine can be imported independently of the user interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import bisect
import math

import numpy as np
import pandas as pd
from numpy.polynomial import Polynomial as Poly


@dataclass(frozen=True)
class Beam:
    length: float
    a: float
    b: float  # Coordinate from the LEFT, not the right-hand offset.
    od: float
    id: float
    young: float
    allowable: float = 0.0

    @property
    def inertia(self):
        return math.pi * (self.od**4 - self.id**4) / 64.0

    @property
    def c(self):
        return self.od / 2.0

    @property
    def modulus(self):
        return self.inertia / self.c

    @property
    def ei(self):
        return self.young * self.inertia


@dataclass(frozen=True)
class Load:
    name: str
    kind: str  # "point" or "uniform"
    force: float  # TOTAL force, positive upward, negative downward.
    start: float
    end: float | None = None

    @property
    def finish(self):
        return self.start if self.kind == "point" else float(self.end)

    @property
    def center(self):
        return self.start * 0.5 + self.finish * 0.5

    @property
    def intensity(self):
        return self.force / (self.finish - self.start) if self.kind == "uniform" else None


@dataclass(frozen=True)
class EndTransfer:
    name: str
    end_x: float
    cg_x: float
    force: float

    @property
    def couple(self):
        """External moment at the welded end, counterclockwise positive."""
        return (self.cg_x - self.end_x) * self.force


def loads_on_tube(length, loads):
    """Keep loads on the tube and transfer outboard portions to their welded ends."""
    on_tube, end_transfers = [], []
    for load in loads:
        # Only a uniform load can cross a tube end. Split its total force in
        # proportion to length so the part on the tube stays distributed.
        cuts = [x for x in (0.0, length) if load.start < x < load.finish]
        portions = [load]
        if cuts:
            edges = [load.start, *cuts, load.finish]
            width = load.finish - load.start
            portions = [
                Load(load.name, "uniform", load.force * ((hi - lo) / width), lo, hi)
                for lo, hi in zip(edges, edges[1:])
            ]
        for part in portions:
            if 0.0 <= part.start and part.finish <= length:
                on_tube.append(part)
            else:
                end_x = 0.0 if part.start < 0.0 else length
                end_transfers.append(EndTransfer(part.name, end_x, part.center, part.force))
    return on_tube, end_transfers


@dataclass
class Piece:
    left: float  # normalized t = x / L
    right: float
    polynomials: dict[str, Poly]


@dataclass
class Critical:
    x: float
    value: float
    side: str = ""
    kinds: set[str] = field(default_factory=set)


@dataclass
class Solution:
    beam: Beam
    loads: list[Load]
    ra: float
    rb: float
    ca: float
    cb: float
    k1: float
    k0: float
    terms: list[tuple[float, int, float]]
    pieces: list[Piece]
    matrix: np.ndarray
    rhs: np.ndarray
    unknowns: np.ndarray
    condition: float
    end_transfers: list[EndTransfer] = field(default_factory=list)

    def at(self, x, quantity="moment", side="right"):
        t = min(1.0, max(0.0, float(x) / self.beam.length))
        edges = [p.right for p in self.pieces]
        i = bisect.bisect_left(edges, t) if side == "left" else bisect.bisect_right(edges, t)
        p = self.pieces[min(i, len(self.pieces) - 1)]
        value = float(p.polynomials[quantity](t))
        return abs(value) if quantity == "stress" else value


def validate(beam: Beam, loads: list[Load]):
    numbers = [beam.length, beam.a, beam.b, beam.od, beam.id, beam.young, beam.allowable]
    if not all(math.isfinite(v) for v in numbers):
        raise ValueError("All geometry and material inputs must be finite numbers.")
    if beam.length <= 0 or beam.young <= 0:
        raise ValueError("Tube length and Young's modulus must be greater than zero.")
    if not 0 <= beam.a < beam.b <= beam.length:
        raise ValueError("Support positions must satisfy 0 ≤ A < B ≤ tube length.")
    if not 0 <= beam.id < beam.od:
        raise ValueError("Diameters must satisfy 0 ≤ ID < OD.")
    if beam.allowable < 0:
        raise ValueError("Allowable stress must be zero or positive.")
    try:
        section_values=[beam.inertia,beam.modulus,beam.ei]
    except OverflowError as error:
        raise ValueError("The section dimensions exceed the numerical range.") from error
    if not all(math.isfinite(v) and v>0 for v in section_values):
        raise ValueError("Section properties and bending stiffness must be finite and positive.")
    for load in loads:
        if load.kind not in ("point", "uniform"):
            raise ValueError(f"{load.name}: unrecognized load type.")
        if load.kind == "uniform" and load.end is None:
            raise ValueError(f"{load.name}: enter the end of the uniform load.")
        if not all(math.isfinite(v) for v in [load.force, load.start, load.finish]):
            raise ValueError(f"{load.name}: enter finite load values and positions.")
        if load.kind == "uniform" and load.finish <= load.start:
            raise ValueError(f"{load.name}: uniform-load end must be greater than its start.")
    left = min([0.0] + [load.start for load in loads])
    right = max([beam.length] + [load.finish for load in loads])
    if not math.isfinite(right - left):
        raise ValueError("The distance between the outermost load positions exceeds the numerical range.")


def bracket(t, position, order):
    return max(float(t) - position, 0.0) ** order


def integrated_terms(terms, t, integrations):
    value = 0.0
    for position, order, coefficient in terms:
        multiplier = math.factorial(order) / math.factorial(order + integrations)
        value += coefficient * multiplier * bracket(t, position, order + integrations)
    return value


def active_polynomial(terms, middle, integrations=0):
    result = Poly([0.0])
    for position, order, coefficient in terms:
        if middle > position:
            multiplier = math.factorial(order) / math.factorial(order + integrations)
            result += coefficient * multiplier * Poly([-position, 1.0]) ** (order + integrations)
    return result


def solve_beam(beam: Beam, loads: list[Load]) -> Solution:
    """Solve six equilibrium/compatibility equations; no equal-reaction shortcut.

    Unknowns are [R_A L, R_B L, C_A, C_B, K1, K0]. Normalized t=x/L
    avoids powers of a long dimensional beam length in the linear system.
    EI*theta/L = integral(M dt)+K1; EI*v/L² = integral²(M dt)+K1*t+K0.
    """
    validate(beam, loads)
    active = [load for load in loads if load.force != 0.0]
    L = beam.length
    a, b = beam.a / L, beam.b / L
    on_tube, end_transfers = loads_on_tube(L, active)
    load_terms = []
    for load in on_tube:
        if load.kind == "point":
            load_terms.append((load.start / L, 1, load.force * L))
        else:
            q = load.intensity
            load_terms.extend([(load.start / L, 2, q * L**2 / 2),
                               (load.finish / L, 2, -q * L**2 / 2)])
    for transfer in end_transfers:
        t_end = transfer.end_x / L
        load_terms.extend([(t_end, 1, transfer.force * L), (t_end, 0, -transfer.couple)])
    # Whole-assembly equilibrium uses the original CGs, including the offsets.
    # The piecewise tube equations above use the equivalent end actions once.
    matrix = [[1., 1., 0., 0., 0., 0.], [a, b, 1., 1., 0., 0.]]
    rhs = [-L * sum(l.force for l in active),
           -sum(l.force * l.center for l in active)]
    for t in (a, b):
        da, db = max(t - a, 0.0), max(t - b, 0.0)
        matrix.append([da**2 / 2, db**2 / 2, -da, -db, 1., 0.])
        rhs.append(-integrated_terms(load_terms, t, 1))
        matrix.append([da**3 / 6, db**3 / 6, -da**2 / 2, -db**2 / 2, t, 1.])
        rhs.append(-integrated_terms(load_terms, t, 2))
    matrix, rhs = np.asarray(matrix), np.asarray(rhs)
    if not np.isfinite(rhs).all():
        raise ValueError("The load and length combination exceeds the numerical range.")
    condition = float(np.linalg.cond(matrix))
    if not math.isfinite(condition) or condition > 1e14:
        raise ValueError("The support spacing is too small relative to tube length for a stable calculation.")
    u = np.linalg.solve(matrix, rhs)
    # Suppress machine-precision remnants, e.g. a force applied exactly at a
    # clamp must not generate spurious micro-peaks on an unloaded tube.
    roundoff = max(sum(abs(l.force)*L for l in active), 1e-300) * 1e-14
    u[np.abs(u) < roundoff] = 0.0
    ra, rb, ca, cb, k1, k0 = u[0] / L, u[1] / L, *u[2:]
    raw_terms = load_terms + [(a, 1, u[0]), (b, 1, u[1]), (a, 0, -ca), (b, 0, -cb)]
    grouped = {}
    for position, order, coefficient in raw_terms:
        grouped.setdefault((position, order), []).append(coefficient)
    terms = [(position, order, math.fsum(coefficients))
             for (position, order), coefficients in grouped.items()
             if abs(math.fsum(coefficients)) > roundoff]
    edges = sorted(set([0., 1., a, b] + [v for l in on_tube for v in (l.start / L, l.finish / L)]))
    pieces = []
    for left, right in zip(edges, edges[1:]):
        mid = (left + right) / 2
        m = active_polynomial(terms, mid)
        # Derivative within an open interval excludes applied-couple impulses.
        v = m.deriv() / L
        theta = (active_polynomial(terms, mid, 1) + Poly([k1])) * (L / beam.ei)
        displacement = (active_polynomial(terms, mid, 2) + Poly([k0, k1])) * (L**2 / beam.ei)
        pieces.append(Piece(left, right, {"moment": m, "shear": v,
                                         "rotation": theta, "deflection": displacement,
                                         "stress": m / beam.modulus}))
    return Solution(beam, active, ra, rb, ca, cb, k1, k0, terms, pieces,
                    matrix, rhs, u, condition, end_transfers)


def real_roots(poly: Poly, left, right):
    scale = max(np.max(np.abs(poly.coef)), 1e-300)
    p = poly.trim(tol=scale * 1e-13)
    if p.degree() <= 0:
        return []
    roots = []
    for root in p.roots():
        if abs(np.imag(root)) <= 1e-8:
            t = float(np.real(root))
            if left + 1e-10 < t < right - 1e-10:
                if not roots or all(abs(t - r) > 1e-8 for r in roots):
                    roots.append(t)
    return sorted(roots)


def near_change(poly, t, direction, absolute=False):
    """Sign of f(t+epsilon*direction)-f(t), using the first nonzero Taylor term."""
    scale = max(float(np.max(np.abs(poly.coef))), 1e-300)
    tol = scale * 1e-9
    center = float(poly(t))
    for order in range(1, poly.degree() + 1):
        derivative = float(poly.deriv(order)(t))
        if abs(derivative) > tol:
            change = math.copysign(1, derivative) * direction**order
            if absolute:
                return 1 if abs(center) <= tol else change * math.copysign(1, center)
            return int(change)
    return 0


def critical_points(solution: Solution, quantity: str) -> list[Critical]:
    """Analytic extrema, one-sided jumps and governing endpoints, not sample labels."""
    L = solution.beam.length
    absolute = quantity == "stress"
    points: list[Critical] = []
    candidates: list[Critical] = []

    def value(piece, t):
        y = float(piece.polynomials[quantity](t))
        return abs(y) if absolute else y

    def add(x, y, kind, side=""):
        for old in points:
            if abs(old.x - x) <= L * 1e-9 and old.side == side:
                old.kinds.add(kind)
                return old
        new = Critical(float(x), float(y), side, {kind})
        points.append(new)
        return new

    def classify(x, y, left_change, right_change, side=""):
        if left_change >= 0 and right_change >= 0 and (left_change or right_change):
            add(x, y, "local minimum", side)
        if left_change <= 0 and right_change <= 0 and (left_change or right_change):
            add(x, y, "local maximum", side)

    for p in solution.pieces:
        polynomial = p.polynomials[quantity]
        roots = real_roots(polynomial.deriv(), p.left, p.right)
        if absolute:
            roots = sorted(set(roots + real_roots(polynomial, p.left, p.right)))
        for t in roots:
            y = value(p, t)
            candidates.append(Critical(t * L, y))
            classify(t * L, y, near_change(polynomial, t, -1, absolute),
                     near_change(polynomial, t, 1, absolute))
        for t, side in [(p.left, "right"), (p.right, "left")]:
            candidates.append(Critical(t * L, value(p, t), side))

    values = [p.value for p in candidates]
    scale = max(max((abs(v) for v in values), default=0), 1e-300)
    tolerance = scale * 1e-8 + 1e-18
    for left, right in zip(solution.pieces, solution.pieces[1:]):
        t = left.right
        yl, yr = value(left, t), value(right, t)
        if abs(yl - yr) > tolerance:
            add(t * L, yl, "jump", "left")
            add(t * L, yr, "jump", "right")
        else:
            classify(t * L, (yl + yr) / 2,
                     near_change(left.polynomials[quantity], t, -1, absolute),
                     near_change(right.polynomials[quantity], t, 1, absolute))
    first, last = solution.pieces[0], solution.pieces[-1]
    classify(0, value(first, 0), 0, near_change(first.polynomials[quantity], 0, 1, absolute))
    classify(L, value(last, 1), near_change(last.polynomials[quantity], 1, -1, absolute), 0)
    # A completely flat diagram has no unique peak to annotate.
    if max(values, default=0) - min(values, default=0) <= tolerance:
        return []
    for target, label in [(min(values), "global minimum"), (max(values), "global maximum")]:
        existing = next((p for p in points if abs(p.value - target) <= tolerance), None)
        if existing:
            existing.kinds.add(label)
        else:
            c = next(p for p in candidates if abs(p.value - target) <= tolerance)
            add(c.x, c.value, label, c.side)
    for c in points:
        if abs(c.value) <= scale * 1e-12:
            c.value = 0.0
    return sorted(points, key=lambda p: (p.x, p.value, p.side))


def peak(solution, quantity):
    points = critical_points(solution, quantity)
    if not points:
        return Critical(0., solution.at(0, quantity), "right", {"constant diagram"})
    return max(points, key=lambda p: abs(p.value))


def check_equilibrium(solution):
    b = solution.beam
    force_scale = max(1., sum(abs(l.force) for l in solution.loads))
    moment_scale = max(1., force_scale * b.length, abs(solution.ca), abs(solution.cb))
    items = [
        ("Vertical force balance", solution.ra + solution.rb + sum(l.force for l in solution.loads), "lbf", force_scale * 1e-8),
        ("Moment balance about left end", solution.ca + solution.cb + solution.ra*b.a + solution.rb*b.b
         + sum(l.force*l.center for l in solution.loads), "lbf·in", moment_scale * 1e-8),
    ]
    for name, x in [("A", b.a), ("B", b.b)]:
        items.append((f"{name}: vertical displacement", solution.at(x, "deflection"), "in", 1e-8))
        items.append((f"{name}: rotation", solution.at(x, "rotation"), "rad", 1e-8))
    return [{"Check": name, "Residual": number, "Units": unit,
             "Tolerance": tol, "Pass": abs(number) <= tol} for name, number, unit, tol in items]


def samples(solution, quantity, per_piece=100):
    rows = []
    L = solution.beam.length
    critical = critical_points(solution, quantity)
    for i, p in enumerate(solution.pieces):
        ts = sorted(set(np.linspace(p.left, p.right, per_piece).tolist()
                        + [c.x / L for c in critical if p.left < c.x / L < p.right]))
        ys = p.polynomials[quantity](ts)
        if quantity == "stress":
            ys = np.abs(ys)
        rows.append((np.asarray(ts) * L, np.asarray(ys)))
    return rows


def export_csv(solution):
    rows = []
    L = solution.beam.length
    for i, p in enumerate(solution.pieces):
        ts = sorted(set(np.linspace(p.left, p.right, 100).tolist() +
                        [c.x/L for q in ("moment", "shear", "stress", "deflection")
                         for c in critical_points(solution, q) if p.left < c.x/L < p.right]))
        for j, t in enumerate(ts):
            row = {"interval": i + 1, "x_in": t * L,
                   "side": "right" if j == 0 else "left" if j == len(ts)-1 else "interior"}
            for q, col in [("moment", "moment_lbf_in"), ("shear", "shear_lbf"),
                           ("stress", "bending_stress_magnitude_psi"),
                           ("deflection", "deflection_upward_in"), ("rotation", "rotation_rad")]:
                y = float(p.polynomials[q](t))
                row[col] = abs(y) if q == "stress" else y
            rows.append(row)
    return pd.DataFrame(rows).to_csv(index=False)


def number(value, digits=5):
    if abs(value) < 1e-12:
        return "0"
    if abs(value)<10**(-digits):
        return f"{value:.3g}"
    return f"{value:,.{digits}f}".rstrip("0").rstrip(".")


QUANTITIES = {
    "moment": ("Bending moment", "lbf·in", "#2463aa"),
    "shear": ("Shear force", "lbf", "#b46718"),
    "deflection": ("Vertical deflection", "in", "#168063"),
    "stress": ("Bending-stress magnitude", "psi", "#7b4ab6"),
}


def make_diagram(solution, quantity):
    import plotly.graph_objects as go

    title, unit, color = QUANTITIES[quantity]
    fig = go.Figure()
    critical = critical_points(solution, quantity)
    display_zero = max((abs(c.value) for c in critical),default=0.0)*1e-12
    all_values = []
    for xs, ys in samples(solution, quantity):
        ys=np.where(np.abs(ys)<=display_zero,0.0,ys)
        all_values.extend(ys.tolist())
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color=color, width=2.5),
                                showlegend=False, name=title,
                                hovertemplate=f"x = %{{x:.5f}} in<br>{title} = %{{y:.6g}} {unit}<extra></extra>"))
    scale = max(max((abs(y) for y in all_values), default=0), 1e-300)
    for left, right in zip(solution.pieces, solution.pieces[1:]):
        x = left.right * solution.beam.length
        yl, yr = solution.at(x, quantity, "left"), solution.at(x, quantity, "right")
        if abs(yl - yr) > scale * 1e-8 + 1e-18:
            fig.add_trace(go.Scatter(x=[x, x], y=[yl, yr], mode="lines",
                                    line=dict(color=color, width=1, dash="dot"),
                                    hoverinfo="skip", showlegend=False))
    for x, label in [(solution.beam.a, "A"), (solution.beam.b, "B")]:
        fig.add_vline(x=x, line_width=1, line_dash="dash", line_color="#a5adb7")
        fig.add_annotation(x=x, y=1.03, yref="paper", text=label, showarrow=False,
                           font=dict(color="#596678", size=12))
    if critical:
        fig.add_trace(go.Scatter(x=[c.x for c in critical], y=[c.value for c in critical],
                                mode="markers", marker=dict(size=6, color=color),
                                customdata=[", ".join(sorted(c.kinds)) for c in critical],
                                hovertemplate=f"%{{customdata}}<br>x = %{{x:.5f}} in<br>%{{y:.6g}} {unit}<extra></extra>",
                                showlegend=False))
    low, high = min(all_values, default=0), max(all_values, default=0)
    span = high-low
    if span < max(abs(low), abs(high), 1.) * 1e-10:
        span = max(abs(low), 1.)
    occupied = []
    for i, c in enumerate(critical):
        fraction = c.x / solution.beam.length
        ax = 45 if fraction < 0.09 else -45 if fraction > 0.91 else 0
        options = [-30, 32, -66, 68, -102, 104, -138, 140]
        if quantity=="stress" and c.value==0:
            options=[-30,-66,-102,-138,-174]
        # Keep labels for nearby peaks and two sides of a jump apart.
        for ay in options:
            px = fraction * 850 + ax
            py = (high - c.value) / span * 280 + ay
            box = (px-65, px+65, py-17, py+17)
            if not any(box[0] < b[1] and box[1] > b[0] and box[2] < b[3] and box[3] > b[2] for b in occupied):
                occupied.append(box)
                break
        side = "−" if c.side == "left" else "+" if c.side == "right" else ""
        fig.add_annotation(x=c.x, y=c.value, ax=ax, ay=ay, text=f"<b>{number(c.value, 4)} {unit}</b><br>x = {number(c.x, 5)}{side} in",
                           showarrow=True, arrowhead=0, arrowwidth=0.7, arrowcolor="#a4adb8",
                           bgcolor="rgba(255,255,255,0.94)", borderpad=3,
                           font=dict(color="#263449", size=11), align="center")
    fig.update_layout(height=500 + min(120, max(0, len(critical)-12)*5), template="plotly_white",
                      margin=dict(l=65, r=35, t=65, b=65),
                      xaxis=dict(title="Distance from left end (in)", range=[0, solution.beam.length],
                                 zeroline=False, gridcolor="#eef1f5"),
                      yaxis=dict(title=f"{title} ({unit})", range=[0.0 if quantity=="stress" else low-.34*span, high+.34*span],
                                 zeroline=True, zerolinecolor="#aab1bb", gridcolor="#eef1f5"),
                      font=dict(family="Arial, sans-serif", color="#24344a"),
                      hovermode="closest", paper_bgcolor="white", plot_bgcolor="white")
    return fig


def tube_svg(beam, loads):
    """Dimensioned responsive SVG. Every force is positioned from the left end."""
    width, plot_left, plot_right = 1000., 55., 950.
    active = [l for l in loads if l.force != 0]
    xmin = min([0.0] + [load.start for load in active])
    xmax = max([beam.length] + [load.finish for load in active])

    def xpos(x):
        return plot_left + (x - xmin) / (xmax - xmin) * (plot_right - plot_left)

    x0, x1 = xpos(0), xpos(beam.length)
    occupied = []
    arranged = []
    for load in active:
        start, end = xpos(load.start), xpos(load.finish)
        center = min(870,max(125,(start+end)/2))
        label_left, label_right = max(15, center-115), min(985, center+115)
        left, right = min(start-8, label_left), max(end+8, label_right)
        lane = 0
        while lane < len(occupied) and any(left < e+12 and right > s-12 for s,e in occupied[lane]):
            lane += 1
        if lane == len(occupied):
            occupied.append([])
        occupied[lane].append((left,right))
        arranged.append((load,lane))
    beam_y = 55 + max(1, len(occupied))*65 if active else 55
    dim_boxes = []
    dimensions = []
    boundaries = [0, beam.a, beam.b, beam.length]
    for start, end in zip(boundaries, boundaries[1:]):
        if end-start <= beam.length*1e-12:
            continue
        center = (xpos(start)+xpos(end))/2
        label = number(end-start, 5)+" in"
        box = (center-len(label)*3.7, center+len(label)*3.7)
        lane = 0
        while any(k == lane and box[0] < e+10 and box[1] > s-10 for s,e,k in dim_boxes):
            lane += 1
        dim_boxes.append((*box,lane))
        dimensions.append((start,end,label,lane))
    extra = max((r[3] for r in dimensions),default=0)*28
    height = beam_y + 215 + extra
    ink, muted, blue, red = "#23354b", "#6e7e91", "#2869ae", "#bf493c"
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" width="100%" role="img" aria-label="Tube schematic with two fixed supports, dimensions, and applied loads">',
             '<defs><pattern id="clamp-hatch" width="7" height="7" patternUnits="userSpaceOnUse"><path d="M-1,1 L1,-1 M0,7 L7,0 M6,8 L8,6" stroke="#718194" stroke-width="1"/></pattern>',
             '<marker id="dim-head" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto-start-reverse"><path d="M0,0 L6,3 L0,6 Z" fill="#6e7e91"/></marker>',
             '<marker id="point-head" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#bf493c"/></marker>',
             '<marker id="uniform-head" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="#2869ae"/></marker></defs>',
             '<style>text{font-family:Arial,sans-serif;font-size:14px;fill:#23354b}.dim{fill:#6e7e91;font-size:13px}.load{font-size:13px;font-weight:500}</style>',
             f'<rect width="100%" height="100%" fill="white"/>']

    def line(xa,ya,xb,yb,color=muted,stroke=1,extra=""):
        parts.append(f'<line x1="{xa:.5f}" y1="{ya:.5f}" x2="{xb:.5f}" y2="{yb:.5f}" stroke="{color}" stroke-width="{stroke}" {extra}/>')

    for load,lane in arranged:
        start,end=xpos(load.start),xpos(load.finish)
        y=beam_y-45-lane*65
        color,marker=(red,"point-head") if load.kind=="point" else (blue,"uniform-head")
        center=min(870,max(125,(start+end)/2))
        arrow="↑" if load.force>0 else "↓"
        title=f"{load.name} · {number(abs(load.force),4)} lbf {arrow}"
        position=f"x = {number(load.start,5)} in" if load.kind=="point" else f"{number(load.start,5)} to {number(load.finish,5)} in"
        parts.append(f'<text x="{center:.3f}" y="{y-24:.3f}" text-anchor="middle" class="load">{escape(title)}</text>')
        parts.append(f'<text x="{center:.3f}" y="{y-7:.3f}" text-anchor="middle" class="dim">{escape(position)}</text>')
        arrows=[start] if load.kind=="point" else np.linspace(start,end,max(2,int((end-start)/38)+1))
        if load.kind=="uniform":
            line(start,y,end,y,color,1.5)
        for x in arrows:
            ya,yb=(y,beam_y-9) if load.force<0 else (beam_y-9,y)
            line(x,ya,x,yb,color,1.8,f'marker-end="url(#{marker})"')
    if xmin < 0:
        line(plot_left,beam_y,x0,beam_y,muted,2,'stroke-dasharray="5 4"')
    if xmax > beam.length:
        line(x1,beam_y,plot_right,beam_y,muted,2,'stroke-dasharray="5 4"')
    line(x0,beam_y,x1,beam_y,ink,8)
    for pos,label in [(beam.a,"A"),(beam.b,"B")]:
        xx=xpos(pos)
        parts.append(f'<rect x="{xx-6}" y="{beam_y-15}" width="12" height="35" fill="#eff3f7" stroke="{ink}"/>')
        parts.append(f'<rect x="{xx-6}" y="{beam_y-15}" width="12" height="35" fill="url(#clamp-hatch)"/>')
        label_y=beam_y+43+(20 if label=="B" and xpos(beam.b)-xpos(beam.a)<65 else 0)
        parts.append(f'<text x="{xx}" y="{label_y}" text-anchor="middle">{label} · Fixed</text>')
    for end in [x0,x1]:
        line(end,beam_y-7,end,beam_y+7,ink,1.4)
    def dimension(start,end,y,label):
        left,right=xpos(start),xpos(end)
        for xx in [left,right]:
            line(xx,beam_y+55,xx,y+6,"#c2cad4",.8)
        line(left,y,right,y,muted,1,'marker-start="url(#dim-head)" marker-end="url(#dim-head)"')
        parts.append(f'<text class="dim" x="{(left+right)/2}" y="{y-9}" text-anchor="middle">{escape(label)}</text>')
    for start,end,label,lane in dimensions:
        dimension(start,end,beam_y+90+lane*28,label)
    dimension(0,beam.length,beam_y+145+extra,number(beam.length,5)+" in tube length")
    parts.append(f'<text x="{x0}" y="{height-18}" class="dim" text-anchor="end">x = 0</text>')
    label_y = height - 40 if x1 - x0 < 100 else height - 18
    anchor = "end" if x1 > 865 else "start"
    parts.append(f'<text x="{x1}" y="{label_y}" class="dim" text-anchor="{anchor}">x = {number(beam.length,5)} in</text>')
    if not active:
        parts.append(f'<text x="500" y="24" text-anchor="middle" class="dim">No applied loads</text>')
    parts.append('</svg>')
    return "".join(parts)


def section_svg(beam):
    radius=80.
    inner=radius*beam.id/beam.od
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 260 290" width="100%" role="img" aria-label="Tube cross-section, OD {beam.od:g} inches and ID {beam.id:g} inches">
    <rect width="260" height="290" fill="white"/>
    <defs><marker id="section-arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto-start-reverse"><path d="M0 0 L6 3 L0 6Z" fill="#607186"/></marker></defs>
    <circle cx="130" cy="145" r="80" fill="#e4ecf5" stroke="#23354b" stroke-width="2"/>
    <circle cx="130" cy="145" r="{inner}" fill="white" stroke="#23354b" stroke-width="2"/>
    <g stroke="#8693a4" stroke-width="1"><path d="M50 145V40M210 145V40"/><path d="M{130-inner} 145V251 M{130+inner} 145V251"/></g>
    <g stroke="#607186" marker-start="url(#section-arrow)" marker-end="url(#section-arrow)"><path d="M50 45H210"/><path d="M{130-inner} 246H{130+inner}"/></g>
    <g font-family="Arial,sans-serif" font-size="14" fill="#23354b" text-anchor="middle"><text x="130" y="30">OD {number(beam.od,5)} in</text><text x="130" y="271">ID {number(beam.id,5)} in</text></g>
    </svg>'''


def latex_number(value, precision=7):
    if abs(value)<1e-12:
        return "0"
    s=f"{value:.{precision}g}"
    if "e" in s:
        base,exp=s.split("e")
        return rf"{base}\times10^{{{int(exp)}}}"
    return s


def polynomial_latex(poly, variable="u"):
    scale=max(float(np.max(np.abs(poly.coef))),1e-300)
    terms=[]
    for power,coefficient in enumerate(poly.coef):
        if abs(coefficient) < scale*1e-11:
            continue
        sign="-" if coefficient<0 else "+"
        factor=latex_number(abs(coefficient))
        term=factor if power==0 else factor+variable+(rf"^{{{power}}}" if power>1 else "")
        terms.append((sign,term))
    if not terms:
        return "0"
    first_sign,first=terms[0]
    return ("-" if first_sign=="-" else "")+first+"".join(sign+term for sign,term in terms[1:])


def render_calculations(solution):
    import streamlit as st

    b=solution.beam
    st.subheader("Inputs and section properties")
    st.caption("Units: in, lbf, psi. All force and deflection signs are positive upward; support couples are counterclockwise positive. Bending moment is sagging positive.")
    st.latex(rf"L={latex_number(b.length)},\quad A={latex_number(b.a)},\quad B={latex_number(b.b)},\quad E={latex_number(b.young)}")
    st.latex(rf"I=\frac{{\pi}}{{64}}(D^4-d^4)=\frac{{\pi}}{{64}}({latex_number(b.od)}^4-{latex_number(b.id)}^4)={latex_number(b.inertia)}\;\mathrm{{in}}^4")
    st.latex(rf"c=D/2={latex_number(b.c)}\;\mathrm{{in}},\qquad Z=I/c={latex_number(b.modulus)}\;\mathrm{{in}}^3,\qquad EI={latex_number(b.ei)}\;\mathrm{{lbf\,in}}^2")
    st.subheader("Load preparation")
    if not solution.loads:
        st.write("No nonzero loads are applied.")
    else:
        rows=[]
        for load in solution.loads:
            rows.append({"Load":load.name,"Type":load.kind,"Signed total force (lbf)":load.force,
                         "Start / point x (in)":load.start,"End x (in)":load.finish,
                         "Centroid x (in)":load.center,"Signed intensity (lbf/in)":load.intensity})
            if load.kind=="uniform":
                st.latex(rf"q_{{y}}=\frac{{{latex_number(load.force)}}}{{{latex_number(load.finish)}-{latex_number(load.start)}}}={latex_number(load.intensity)}\;\mathrm{{lbf/in}}")
        st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
    if solution.end_transfers:
        st.subheader("Loads transferred by end fittings")
        st.write("Each welded fitting transfers its vertical load and its moment about the tube end. "
                 "For a uniform load crossing an end, this table shows only the portion beyond that end.")
        st.latex(r"C_e = F_y (x_{\mathrm{CG}} - x_e)")
        st.dataframe(pd.DataFrame([{
            "Load": transfer.name,
            "Tube end": "Left" if transfer.end_x == 0 else "Right",
            "CG x (in)": transfer.cg_x,
            "End x (in)": transfer.end_x,
            "Signed offset (in)": transfer.cg_x - transfer.end_x,
            "End force, up + (lbf)": transfer.force,
            "End moment, CCW + (lbf·in)": transfer.couple,
        } for transfer in solution.end_transfers]),hide_index=True,width="stretch")
    st.subheader("Full support reactions and fixed-support constraints")
    st.write("The two actual support reactions are solved independently. No equality between them is imposed.")
    st.latex(r"R_A+R_B+\sum_i F_{y,i}=0")
    st.latex(r"C_A+C_B+R_A A+R_B B+\sum_i F_{y,i}\bar{x}_i=0")
    st.latex(r"EI\,v''(x)=M(x),\qquad v(A)=v'(A)=v(B)=v'(B)=0")
    st.dataframe(pd.DataFrame([
        {"Quantity":"R_A","Value":solution.ra,"Units":"lbf","Positive direction":"Upward"},
        {"Quantity":"R_B","Value":solution.rb,"Units":"lbf","Positive direction":"Upward"},
        {"Quantity":"C_A","Value":solution.ca,"Units":"lbf·in","Positive direction":"Counterclockwise"},
        {"Quantity":"C_B","Value":solution.cb,"Units":"lbf·in","Positive direction":"Counterclockwise"},
    ]),hide_index=True,width="stretch")
    st.write("The moment along the tube includes the support reactions, loads on the tube, and any fitting end actions.")
    st.latex(r"\begin{aligned}M(x)={}&R_A\langle x-A\rangle+R_B\langle x-B\rangle-C_AH(x-A)-C_BH(x-B)\\&+\sum_iF_{y,i}\langle x-p_i\rangle+\sum_j\frac{q_{y,j}}2[\langle x-s_j\rangle^2-\langle x-e_j\rangle^2]\\&+\sum_e\left[F_{y,e}\langle x-x_e\rangle-C_eH(x-x_e)\right]\end{aligned}")
    st.caption("The bracket is zero before its application position. H is a step; the values on the two sides of a support couple are evaluated separately.")
    with st.expander("Numerical equilibrium and compatibility system"):
        st.write("Normalize position with t = x/L. This changes numerical scaling, not the physical beam model.")
        st.latex(r"\mathbf{u}=[R_A L,\ R_B L,\ C_A,\ C_B,\ K_1,\ K_0]^T,\qquad \mathbf{A}\mathbf{u}=\mathbf{b}")
        st.latex(r"\theta=\frac{L}{EI}\left[\int M(t)\,dt+K_1\right],\qquad v=\frac{L^2}{EI}\left[\iint M(t)\,dt^2+K_1t+K_0\right]")
        labels=["Force balance × L","Moment balance","Rotation at A","Displacement at A","Rotation at B","Displacement at B"]
        frame=pd.DataFrame(solution.matrix,columns=["R_A L","R_B L","C_A","C_B","K1","K0"],index=labels)
        frame["Right-hand side"]=solution.rhs
        st.dataframe(frame,width="stretch")
        st.dataframe(pd.DataFrame({"Unknown":["R_A L","R_B L","C_A","C_B","K1","K0"],"Solution":solution.unknowns}),hide_index=True,width="stretch")
    st.subheader("Numerical equations in every interval")
    st.caption("Each interval has its own local coordinate u = x − interval start, measured in inches. Values are shown with seven significant digits; analysis uses full precision.")
    for i,p in enumerate(solution.pieces):
        x0,x1=p.left*b.length,p.right*b.length
        with st.expander(f"Interval {i+1}: {number(x0)} to {number(x1)} in"):
            st.latex(rf"u=x-{latex_number(x0)},\qquad 0\le u\le {latex_number(x1-x0)}")
            local=Poly([p.left,1/b.length])
            for quantity,symbol,unit in [("shear","V","lbf"),("moment","M",r"lbf\,in"),
                                         ("rotation",r"\theta","rad"),("deflection","v","in")]:
                st.latex(rf"{symbol}(u)={polynomial_latex(p.polynomials[quantity](local))}\quad[\mathrm{{{unit}}}]")
            st.latex(rf"\sigma_b(u)=\frac{{|M(u)|}}{{{latex_number(b.modulus)}}}\quad[\mathrm{{psi}}]")
    st.subheader("Critical-point calculations")
    st.latex(r"\frac{dM}{dx}=V=0\quad\text{for interior moment extrema};\qquad\frac{dv}{dx}=\theta=0\quad\text{for deflection extrema}")
    st.write("Polynomial roots inside each interval are checked along with interval boundaries. Stress-zero locations are also checked as minima of stress magnitude. Both one-sided values are retained at genuine jumps.")
    rows=[]
    for quantity,(title,unit,_) in QUANTITIES.items():
        for c in critical_points(solution,quantity):
            rows.append({"Diagram":title,"x from left (in)":c.x,"Side":c.side or "continuous",
                         "Value":c.value,"Units":unit,"Reason":", ".join(sorted(c.kinds))})
    if rows:
        st.dataframe(pd.DataFrame(rows),hide_index=True,width="stretch")
    m=peak(solution,"moment")
    st.latex(rf"\sigma_{{b,\max}}=\frac{{|M|_{{\max}}c}}{{I}}=\frac{{{latex_number(abs(m.value))}\times {latex_number(b.c)}}}{{{latex_number(b.inertia)}}}={latex_number(abs(m.value)/b.modulus)}\;\mathrm{{psi}}")
    if b.allowable>0:
        stress=abs(m.value)/b.modulus
        st.latex(rf"\text{{Utilization}}=\frac{{{latex_number(stress)}}}{{{latex_number(b.allowable)}}}={latex_number(stress/b.allowable)}")
        if stress>0:
            st.latex(rf"\text{{Allowable-to-calculated ratio}}={latex_number(b.allowable/stress)}")
    st.subheader("Verification")
    checks=check_equilibrium(solution)
    st.dataframe(pd.DataFrame(checks),hide_index=True,width="stretch")
    if all(row["Pass"] for row in checks):
        st.success("Force balance, moment balance, and all four fixed-support conditions pass.")
    else:
        st.error("A numerical verification check failed. Review the inputs and conditioning before using the results.")
    with st.expander("Model, scope, and references"):
        st.markdown("""- Straight, constant-section, homogeneous, linear elastic Euler–Bernoulli beam with small deflections.
- Exactly two ideal fixed supports restrain both vertical movement and bending rotation.
- An outboard load acts through the welded end on that side. Tube diagrams cover x = 0 to L. The model assumes the fitting carries the load to that end alone. Fitting deformation and weld stresses are outside its scope.
- Loads act vertically in the bending plane. Uniform-load inputs are total force over their interval; tube self-weight is a separate full-length downward load.
- Reported stress is nominal longitudinal bending stress. Transverse shear stress, torsion, axial loads, local clamp/contact stresses, and stress concentrations are outside this model.
- The entered allowable stress is a user-supplied comparison value; the app does not determine an ASME allowable or certify a shipping arrangement.
- [MIT — internal forces and section cuts](https://ocw.mit.edu/courses/2-001-mechanics-materials-i-fall-2006/0b739c732b57ee6d4221b5cfce732769_lec5.pdf)
- [MIT — moment, curvature, compatibility and indeterminate beams](https://ocw.mit.edu/courses/2-001-mechanics-materials-i-fall-2006/e5a0d036c217b7c10b335ab17b56dcad_lec21.pdf)
- [University of Alberta — loads, shear, moment and concentrated couples](https://engcourses-uofa.ca/books/statics/internal-forces/relationships-between-loads-shears-and-moments/)
- [Engineering Statics — equivalent forces and couples](https://engineeringstatics.org/statically-equivalent-systems.html)
""")


MODEL_INPUT_DEFAULTS = {
    "tube_length": None,
    "support_a": None,
    "support_b_offset": None,
    "tube_od": None,
    "tube_id": None,
    "young_modulus": 29_000_000.0,  # Structural steel, psi.
    "allowable_stress": None,
    "tube_weight": None,
}


def initialize_state():
    import streamlit as st
    for key, value in MODEL_INPUT_DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("force_ids", [])
    st.session_state.setdefault("next_force_id", 1)
    # Preserve temporarily hidden point/range fields when the type is switched.
    # Assignment occurs before any widgets are rendered, never after them.
    for ident in st.session_state.force_ids:
        for suffix,default in force_defaults().items():
            key=f"force_{ident}_{suffix}"
            st.session_state[key]=st.session_state.get(key,default)


def force_defaults():
    return {"kind":"Point load","magnitude":None,"direction":"Downward",
            "position":None,"full":False,"start":None,"end":None}


def add_force():
    import streamlit as st
    ident=st.session_state.next_force_id
    st.session_state.next_force_id=ident+1
    st.session_state.force_ids=st.session_state.force_ids+[ident]
    for suffix,value in force_defaults().items():
        st.session_state[f"force_{ident}_{suffix}"]=value


def remove_force(ident):
    import streamlit as st
    st.session_state.force_ids=[i for i in st.session_state.force_ids if i!=ident]
    for key in list(st.session_state.keys()):
        if key.startswith(f"force_{ident}_"):
            del st.session_state[key]


def reset_inputs():
    import streamlit as st
    # Explicitly assign widget values in the callback so the browser clears
    # the existing fields as well as the server-side inputs.
    st.session_state.update(MODEL_INPUT_DEFAULTS)
    for ident in list(st.session_state.force_ids):
        remove_force(ident)
    st.session_state.next_force_id = 1


def input_panel():
    import streamlit as st
    loads = []
    pending_forces = []
    with st.sidebar:
        heading, actions = st.columns([2, 1], vertical_alignment="center")
        heading.header("Inputs")
        actions.button("Reset", key="reset_inputs", on_click=reset_inputs, width="stretch",
                       help="Clear the model and restore the steel modulus.")
        st.caption("Schematic and results update automatically when an input is committed.")
        st.subheader("Geometry")
        length=st.number_input("Tube length (in)",min_value=0.001,value=None,step=1.0,format="%.5f",persist_state="session", key="tube_length")
        col1,col2=st.columns(2)
        a=col1.number_input("A from left (in)",min_value=0.0,value=None,step=1.0,format="%.5f",persist_state="session", key="support_a")
        offset=col2.number_input("B from right (in)",min_value=0.0,value=None,step=1.0,format="%.5f",persist_state="session", key="support_b_offset")
        st.caption("Both supports fully fixed")
        st.subheader("Cross-section")
        col1,col2=st.columns(2)
        od=col1.number_input("OD (in)",min_value=0.001,value=None,step=0.125,format="%.5f",persist_state="session", key="tube_od")
        id_=col2.number_input("ID (in)",min_value=0.0,value=None,step=0.125,format="%.5f",persist_state="session", key="tube_id")
        st.subheader("Material")
        young=st.number_input("Young's modulus E (psi)",min_value=1.0,value=None,step=100000.0,format="%.0f",persist_state="session", key="young_modulus",
                              help=f"The default is {MODEL_INPUT_DEFAULTS['young_modulus']:,.0f} psi for structural steel. You can enter a material-specific value.")
        allowable=st.number_input("Allowable bending stress (psi)",min_value=0.0,value=None,step=1000.0,format="%.2f",persist_state="session", key="allowable_stress",placeholder="Optional",help="Enter a positive value to compare with the calculated stress.")
        st.subheader("Tube self-weight")
        weight=st.number_input("Total tube weight (lbf)",min_value=0.0,value=None,step=10.0,format="%.4f",persist_state="session", key="tube_weight",placeholder="Optional")
        st.caption("Self-weight acts downward over the tube length. Enter fitting weights as separate loads.")
        if weight and length is not None:
            loads.append(Load("Tube self-weight","uniform",-weight,0.0,length))
        st.subheader("Applied forces")
        st.button("+ Add force",key="add_force",on_click=add_force,width="stretch")
        if st.session_state.force_ids:
            st.caption("Measure x from the left tube end. For a fitting, use its CG position. "
                       "Use negative x beyond the left end or x greater than the tube length beyond the right.")
        for ident in st.session_state.force_ids:
            prefix=f"force_{ident}_"
            name=f"Force {ident}"
            with st.expander(name,expanded=True):
                kind=st.radio("Force type",["Point load","Uniform load"],horizontal=True,persist_state="session", key=prefix+"kind")
                magnitude=st.number_input("Total force (lbf)",min_value=0.0,value=None,step=10.0,format="%.4f",persist_state="session", key=prefix+"magnitude")
                direction=st.radio("Direction",["Downward","Upward"],horizontal=True,persist_state="session", key=prefix+"direction")
                signed_force=None if magnitude is None else magnitude * (1 if direction=="Upward" else -1)
                if kind=="Point load":
                    start=st.number_input("Position from left (in)",value=None,step=1.0,format="%.5f",persist_state="session", key=prefix+"position")
                    end=start
                else:
                    full=st.checkbox("Full tube length",persist_state="session", key=prefix+"full")
                    if full:
                        start,end=0.0,length
                        if length is not None:
                            st.caption(f"From x = 0 to {number(length)} in.")
                    else:
                        c1,c2=st.columns(2)
                        start=c1.number_input("Start from left (in)",value=None,step=1.0,format="%.5f",persist_state="session", key=prefix+"start")
                        end=c2.number_input("End from left (in)",value=None,step=1.0,format="%.5f",persist_state="session", key=prefix+"end")
                    st.caption("Enter the total force over this interval.")
                if None in (signed_force, start, end):
                    pending_forces.append(name)
                elif kind=="Point load":
                    loads.append(Load(name,"point",signed_force,start))
                else:
                    loads.append(Load(name,"uniform",signed_force,start,end))
                st.button("Remove force",key=prefix+"remove",on_click=remove_force,args=(ident,),width="stretch")
        calculate=st.button("Calculate",type="primary",width="stretch",key="calculate")
    beam = None
    if None not in (length, a, offset, od, id_, young):
        beam = Beam(length,a,length-offset,od,id_,young,allowable or 0.0)
    return beam, loads, pending_forces, calculate


def critical_location(beam, c):
    for name,x in [("A",beam.a),("B",beam.b)]:
        if abs(c.x-x)<beam.length*1e-8:
            return ("Immediately left of " if c.side=="left" else "Immediately right of " if c.side=="right" else "At ")+name
    if abs(c.x)<beam.length*1e-8:
        return "Left end"
    if abs(c.x-beam.length)<beam.length*1e-8:
        return "Right end"
    return "Interior section"


def render_app():
    import streamlit as st

    st.markdown("""<style>
    .block-container{max-width:1550px;padding-top:1.5rem;padding-bottom:2rem}
    [data-testid="stSidebar"]{min-width:350px;max-width:370px}
    [data-testid="stSidebar"] .block-container{padding-top:1.2rem}
    [data-testid="stSidebar"] h3{font-size:1.04rem;padding-bottom:.2rem}
    [data-testid="stMetricValue"]{font-size:1.5rem}
    @media(max-width:700px){[data-testid="stSidebar"]{min-width:0;max-width:90vw}}
    </style>""",unsafe_allow_html=True)
    initialize_state()
    beam,loads,pending_forces,calculate=input_panel()
    st.title("Tube Load Analyzer")
    st.caption("Two fixed supports · inches · pound-force · psi")
    if beam is None:
        if st.session_state.young_modulus is None:
            st.info("Enter Young’s modulus or use Reset to start a new model with the steel default.")
        else:
            st.info("Enter the tube length, both support positions, OD and ID to start.")
        return
    try:
        validate(beam,loads)
    except ValueError as error:
        st.error(str(error))
        st.stop()
    left,right=st.columns([3.4,1.0],gap="medium")
    with left:
        st.subheader("Tube schematic")
        st.caption("Longitudinal positions are to scale. Vertical arrows show force direction.")
        st.image(tube_svg(beam,loads),width="stretch")
        if any(load.force and (load.start < 0 or load.finish > beam.length) for load in loads):
            st.caption("Dashed extensions show the distances to fitting loads. The solid line is the tube.")
    with right:
        st.subheader("Cross-section")
        st.image(section_svg(beam),width="stretch")
    if pending_forces:
        st.info("Complete or remove the unfinished load entries to see results (" + ", ".join(pending_forces) + ").")
        return
    try:
        solution=solve_beam(beam,loads)
    except (ValueError,np.linalg.LinAlgError) as error:
        st.error(str(error))
        st.stop()
    if calculate:
        st.toast("Results recalculated from the current inputs.")
    has_loads=bool(solution.loads)
    m=peak(solution,"moment")
    d=peak(solution,"deflection")
    stress=abs(m.value)/beam.modulus
    st.subheader("Analysis results")
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Max bending stress",f"{stress:,.2f} psi" if has_loads else "—")
    c2.metric("Max |moment|",f"{abs(m.value):,.2f} lbf·in" if has_loads else "—")
    c3.metric("Max |deflection|",f"{abs(d.value):,.6f} in" if has_loads else "—")
    c4.metric("Critical x from left",f"{number(m.x,5)} in" if has_loads and abs(m.value)>0 else "—")
    if has_loads:
        if m.value!=0:
            st.caption(f"Critical bending section: {critical_location(beam,m)}. Deflection peak: {number(d.x,5)} in from the left end.")
        else:
            st.caption("All sections have zero nominal bending stress; there is no unique critical bending location.")
        if beam.allowable>0:
            if stress<=beam.allowable:
                st.success("Nominal bending stress is within the entered allowable.")
            else:
                st.error("Nominal bending stress exceeds the entered allowable.")
        with st.expander("Support reaction results"):
            st.dataframe(pd.DataFrame({"Support":["A","B"],"Vertical reaction, upward + (lbf)":[solution.ra,solution.rb],
                                       "Reaction moment, CCW + (lbf·in)":[solution.ca,solution.cb]}),hide_index=True,width="stretch")
    tabs=st.tabs(["Bending moment","Shear force","Deflection","Stress","Calculations"])
    captions={"moment":"Positive: sagging. Negative: hogging. Dotted vertical connectors indicate moment jumps.",
              "shear":"Signed internal shear force. Dotted vertical connectors indicate shear jumps.",
              "deflection":"Vertical displacement: positive upward, negative downward.",
              "stress":"Maximum nominal outer-surface bending-stress magnitude along the tube."}
    for tab,quantity in zip(tabs[:4],["moment","shear","deflection","stress"]):
        with tab:
            st.caption(captions[quantity])
            if has_loads:
                st.plotly_chart(make_diagram(solution,quantity),width="stretch",theme=None,
                                key="diagram_"+quantity,config={"displaylogo":False,"scrollZoom":True,
                                "toImageButtonOptions":{"format":"png","filename":"tube_"+quantity,"scale":2}})
                st.caption("Labels mark extrema and genuine jumps only. Hover over a curve to inspect another position.")
            else:
                st.info("Add a nonzero load to view this diagram.")
    with tabs[4]:
        render_calculations(solution)
    st.download_button("Download chart data as CSV",data=export_csv(solution),file_name="beam_stress_chart_data.csv",
                       mime="text/csv",disabled=not has_loads,key="download_csv")


def main():
    import streamlit as st

    st.set_page_config(page_title="Tube Load Analyzer", layout="wide", initial_sidebar_state="expanded")
    render_app()


if __name__=="__main__":
    main()
