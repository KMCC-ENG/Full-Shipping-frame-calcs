# Tube Load Analyzer

## Using the app

- One input panel contains geometry, fixed-support positions, tube OD/ID,
  Young's modulus, an optional allowable bending stress, tube self-weight,
  and all applied forces.
- Young's modulus defaults to **29,000,000 psi** for steel and is editable.
  Every other numeric field starts blank. Enter the tube length, both support
  offsets, OD and ID to start. Enter zero for a support at an end or for a
  solid section's ID. Tube weight and allowable stress are optional.
- **Reset** at the top of the input panel clears the current model and its
  results, removes all added forces, and restores the steel modulus.
- **Add force** creates a removable point or uniform-load entry. Point loads
  need one position. Uniform loads need a start and end, or **Full tube length**.
- Every force has a magnitude in **lbf** and an upward/downward direction.
  For a uniform load, enter its **total force over the interval**, not lbf/in.
- Point and uniform loads can act on the tube or beyond either end. A custom
  uniform load may cross an end. Its entered force covers the entire interval.
- Tube self-weight is a separate full-length downward load. Do not also add
  that same self-weight as an applied uniform force unless it is intentional.
- Committing an input (Enter, leaving the field, or using its step buttons)
  updates the schematic, cross-section, and analysis automatically. The
  Calculate button also recalculates the current model.
- All positions for applied forces are measured from the **left end**.
  Support B uses its **offset from the right end**.
- The schematic follows the actual longitudinal positions. Load arrows show
  direction; their drawn lengths do not encode load magnitude. Read their labels.
- Moment, shear, deflection and stress diagrams label only critical points.
  Hover to inspect other positions; the plot toolbar can export PNG images.
- The stress diagram is the maximum **nominal bending-stress magnitude** at
  each cross-section. It is not von Mises stress.
- All formulas, numerical substitutions, interval equations, reaction solving,
  critical-point tables, and verification checks are in **Calculations**.
- CSV export preserves both one-sided values at discontinuities. Duplicate
  x coordinates with different `side` values are intentional.

### Welded end fittings

Enter a fitting's weight as a downward point load at its center of gravity.
For a 120 in tube, enter `x = -6` for a CG 6 in beyond the left end, or
`x = 126` for a CG 6 in beyond the right end.

The model assumes each fitting carries its load through the welded end on
that side. At that end it applies the signed vertical force and the external
couple `C = F_y (x_CG − x_end)`, with upward force and counterclockwise
moment positive. A 100 lbf downward load at `x = 126` transfers 100 lbf
downward and 600 lbf·in clockwise at the right end. **Calculations** shows
the transfer for each outboard load. For a uniform load crossing an end, the
portion on the tube stays distributed and the portion outside is transferred
at its own centroid.

Dashed extensions on the schematic show the outboard load positions. The
diagrams, critical locations, and CSV cover the physical tube from 0 to L.
The analysis calculates the tube response. Fitting deflection, local weld
stress, and torsion from an out-of-plane offset are outside its scope.

## Worked example for checking

Enter:

- Length: 305.625 in
- A from left: 100.625 in; B from right: 12 in
- OD: 3.96875 in; ID: 3.219 in
- E = 29,000,000 psi (steel default)
- Tube self-weight: 370 lbf
- Add one downward point load: 130.44 lbf at x = 305.625 in

Reference results, using the ideal fixed-support model:

| Quantity | Value |
| --- | ---: |
| R_A, upward positive | 238.64621677 lbf |
| R_B, upward positive | 261.79378323 lbf |
| C_A, CCW positive | -2371.16215065 lbf·in |
| C_B, CCW positive | -2105.46301295 lbf·in |
| M immediately left of A | -6129.07080777 lbf·in |
| M immediately right of A / left of B | -3757.90865712 lbf·in |
| M at middle-span midpoint | +1878.95432856 lbf·in |
| M immediately right of B | -1652.44564417 lbf·in |

## Analysis method and scope

The engine integrates signed point and partial uniform loads exactly as
piecewise polynomials. It solves six equations for the two full vertical
support reactions, two external reaction moments and two integration constants:
global force/moment equilibrium and zero displacement/rotation at A and B.
It does **not** assume the total support reactions are equal. Extrema are found
from polynomial roots, rather than from plot samples.

Assumptions: straight, constant cross-section, homogeneous linear elastic
Euler–Bernoulli beam; small deflections; two ideal clamps; vertical loads only.
Nominal bending stress excludes axial/torsional stress, transverse shear stress,
local clamp/contact stresses and stress concentrations. An entered allowable is
a user-provided comparison value, not an automatically derived code allowable.
The output is not a shipping qualification or an ASME design certification.

References:

- [MIT — section cuts and internal forces](https://ocw.mit.edu/courses/2-001-mechanics-materials-i-fall-2006/0b739c732b57ee6d4221b5cfce732769_lec5.pdf)
- [MIT — beam compatibility and indeterminate analysis](https://ocw.mit.edu/courses/2-001-mechanics-materials-i-fall-2006/e5a0d036c217b7c10b335ab17b56dcad_lec21.pdf)
- [University of Alberta — shear, moment and applied couples](https://engcourses-uofa.ca/books/statics/internal-forces/relationships-between-loads-shears-and-moments/)
- [Engineering Statics — equivalent forces and couples](https://engineeringstatics.org/statically-equivalent-systems.html)
