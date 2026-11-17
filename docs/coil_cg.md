# Coil Center of Gravity

## Inputs and behavior

- Tube length and component positions use inches. Weights use pound-force (lbf).
- Enter the actual total tube weight. It is uniform over the tube length and
  is counted exactly once.
- The initial model has zero self-weight and no added parts. No weight arrows
  or CG marker appear until a positive weight is entered. Zero total weight
  produces an undefined CG, rather than an assumed midpoint.
- **Add weight** creates a removable named component. Choose **Point weight**
  or **Uniform weight**. All entered weights are nonnegative.
- A point weight belongs at the omitted part's own CG coordinate.
- A uniform weight requires a start and end position or **Full tube length**.
  Enter its **total weight**, not lbf/in. Overlapping intervals are supported.
- All coordinates are measured from the tube's left end: zero is the left
  end, L is the right end, negative is beyond the left end, and a coordinate
  greater than L is beyond the right end. Point positions and uniform
  intervals can extend beyond either end; they are never clipped to the tube.
- When a field is committed (Enter, leaving the field, or its step buttons),
  the schematic and results update automatically. **Calculate** also reruns
  the current inputs. Hidden point/interval fields survive type changes.
- The schematic expands to show all positive weights, using actual horizontal
  positions. Dashed extensions are a coordinate reference. Arrow lengths do
  not encode weight magnitude. A green target marks the calculated assembly CG.
- Results give total weight, additional-parts weight, and signed CG distances
  from both ends. **CG from left** is positive toward the right. **CG from
  right** is positive toward the left; a negative result is beyond the right end.
- **Weight distribution** separates point weights (lbf) from uniform
  intensities (lbf/in) so their vertical units are not mixed.
- **Component summary** lists every entry. **Calculations** contains all
  formulas, substitutions, first moments and the moment check.
- **Download results as CSV** exports component weights, locations, moments,
  weight shares, total weight and CG. **Load example** replaces the current
  inputs with an editable example containing weights beyond both ends.

## Calculation and scope

For each component, use its own center-of-gravity coordinate x_i. The uniform
tube is located at L/2 and a uniform component at (start + end)/2.

```text
Total weight = sum(W_i)
First moment about left tube end = sum(W_i * x_i)
Assembly CG from left = first moment / total weight
```

The engine also checks that the moments about the calculated CG sum to zero
within a floating-point tolerance. No supports or fixed points are required.
The result can lie outside the tube length if the omitted components extend
beyond it. It remains between the extreme positive-weight component CGs.

This is a longitudinal, one-dimensional CG calculation for a straight tube
under uniform gravity. Every added entry is the weight of a represented part;
use actual part CG positions. Only tube length, actual weights and their
positions are needed. Transverse CG
coordinates, local deformation and structural/lifting adequacy are not calculated.

Reference: [NASA Glenn Research Center — Center of Gravity](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/center-of-gravity/).

## Hand-check example

Tube length 100 in, tube weight 100 lbf, plus a 100 lbf point weight at x=0
and a 300 lbf point weight at x=100:

| Result | Value |
| --- | ---: |
| Total assembly weight | 500 lbf |
| Total first moment about left end | 35,000 lbf·in |
| Assembly CG from left end | 70 in |
| Assembly CG from right end | 30 in |

Outside-interval example: a 100 in tube weighing 100 lbf plus a uniform
200 lbf component over x=-60 to x=-20 has total weight 300 lbf and CG x=-10 in.
