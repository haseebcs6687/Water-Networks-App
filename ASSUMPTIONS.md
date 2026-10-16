# ASSUMPTIONS.md – Judgment Calls in core/

This document records every non-obvious decision made while building the
`core/` package for the water-distribution-network PySide6 migration (Step 1).

---

## 1. Tank Inflow Sign Convention

**Decision**: `TANK_INFLOW_SIGN = +1`.

A pipe whose **end** node is a tank contributes `+1` (positive) to the tank
row of the A matrix (inflow is positive). A pipe whose **start** node is a
tank contributes `−1` (outflow is negative). This exactly matches the junction
continuity convention used by the legacy code for junctions.

**Why not the legacy tank sign?**  
The legacy code only wrote `+1` when a tank was the *start* of a pipe and
wrote nothing when a tank was the *end*. This left the tank row all-zero for
networks where water only flows *into* the tank, making those networks appear
singular even when they are well-posed. The corrected sign is a **bug fix**.

**Rationale for +1 = inflow**  
From the mass-balance perspective the tank's state variable (pressure / water
level) is driven by net inflow. Matching the junction sign keeps the physical
interpretation consistent across node types.

**Flipping the sign**: if a future paper revision or regulatory standard
requires outflow-positive, change `TANK_INFLOW_SIGN = +1` to
`TANK_INFLOW_SIGN = −1` in `core/matrices.py`; no other code needs to change.

---

## 2. Tanks Counted as Supply Nodes (Validation)

**Decision**: tanks are treated as supply nodes in the connectivity check
(`validate_network`).

A tank can supply or receive water; it provides a non-trivial boundary
condition (known pressure trajectory). Therefore a component that contains
a tank but no reservoir is treated as *having a supply* and is **not** flagged
as supply-free.

---

## 3. Symbolic String Format (kept from legacy)

The following symbolic strings are kept exactly as in the legacy code:

| Matrix | Entry | String |
|--------|-------|--------|
| G | non-pumped pipe i (1-based) | `f"-C_aQ{i+1}|Q{i+1}|"` |
| G | pumped pipe | `"-S_puG_pu(Q_pu)"` |
| A | non-pumped Pl | `f"c{i+1}"` |
| A | non-pumped Pr | `f"-c{i+1}"` |
| A | pump diagonal | `f"1-s{sym_idx}"` |
| A | pump start pressure | `f"-s{sym_idx}"` |
| A | pump end pressure | `f"s{sym_idx}"` |
| A | pipe end-side flow | `f"1-s{i+1}"` |
| A | pipe end-side Pr | `f"s{i+1}"` |
| A | pipe end-side node | `f"-s{i+1}"` |
| F | reservoir i (0-based) | `f"-P_{chr(97+i)}"` i.e. `-P_a`, `-P_b`, … |

Symbol numbering: `c{i+1}` and `s{i+1}` index over **non-pumped** pipes
(1-based, in creation order); pump symbols continue at `s{N_np + i + 1}` where
`i` is 0-based within the pumped list. This is identical to the legacy
numbering when normal pipes come before pumps.

---

## 4. Column Ordering Bug Fix (ORDER BUG)

**Legacy assumption**: the first `non_pumped` pipes in the input list are the
non-pumped ones, and column indices are derived by parsing the integer suffix
of pipe/node IDs (e.g., `int("P3"[1:])` → 3).

**New approach**: pipes are partitioned into `non_pumped` and `pumped` lists
(preserving creation order within each group). All column indices are derived
from position in those lists via `pipe_flow_col` and `node_col` dictionaries.
No IDs are ever parsed. The resulting matrix is independent of the order in
which pipes were added to the network.

---

## 5. Numeric Pencil Evaluation (s=1, c=1)

**Substitution rules for `numeric_pencil`**:

- All switch variables `s_i` → 1 (all valves open, all pumps on).
- All conductance coefficients `c_i` → 1.
- Expressions like `1-s_i` → 0; `s_i` → 1; `-s_i` → -1; `c_i` → 1.

This represents the fully-activated network state (worst case for regularity
testing: if it is singular here it is structurally singular).

---

## 6. Regularity Check — Tolerance and Sampling

**Method**: evaluate `np.linalg.slogdet(λE − A)` at `_REGULARITY_N_SAMPLES = 8`
complex values of λ, drawn from a **fixed** RNG seed (`_REGULARITY_SEED = 42`).

**Tolerance**: `_REGULARITY_TOL = 1e-7`.  
A pencil is declared regular if `|det| > 1e-7` for at least one sample.

**Why `slogdet`?**  
`slogdet` returns `(sign, log|det|)`. It never overflows for large matrices,
unlike `np.linalg.det`. We check `sign != 0` (non-trivially-zero determinant)
AND `logabsdet > log(tol)`.

**Why multiple samples?**  
A single λ might accidentally coincide with an eigenvalue of a *regular* pencil
and give zero determinant. Using 8 samples from the complex plane (with
non-zero imaginary parts to avoid real eigenvalues) makes a false-negative
extremely unlikely.

**Limitation**: this is a heuristic test, not a formal algebraic rank check.
For production use, a Smith-McMillan form or Kronecker structure analysis
would be more rigorous. That is left for a later step.

---

## 7. Pump Cycle Detection — Cyclomatic Number Method

**Paper method**: merge all supply nodes (reservoirs + tanks) into a single
virtual super-node called `__supply__`, build an undirected multigraph of pump
edges only, and for each connected component compute:

```
cyclomatic_number = E − V + 1
```

where E = number of pump edges, V = number of vertices, and the "+1" assumes
the component is connected (C=1). A cyclomatic number > 0 means there is at
least one independent cycle in the pump sub-graph, which is a structural
problem for the switched-DAE formulation.

**Cross-check**: the rank of the pump-column block of the modified incidence
matrix is also computed. If `rank < number_of_pump_edges` but the cyclomatic
method did not flag a cycle, an additional warning is emitted.

---

## 8. Incidence Matrix Signs

Convention: −1 at the **start** (initial) node of each edge, +1 at the
**end** (terminal) node. Each column therefore sums to 0.

Reference row for the *reduced* incidence: first reservoir, else first tank,
else first node in creation order.

---

## 9. Node ID Auto-Generation

Prefixes: `J` (junction), `T` (tank), `R` (reservoir), `P` (pipe).
Counters track the **maximum issued number**, so manual IDs (supplied via
`id=` keyword) are respected and auto-generated IDs never collide with them
after `from_dict` round-trips.

---

## 10. Physical parameters and .wnet v2

- **SI Units**: All physical network quantities are expressed in standard SI units: pipe length ($m$), pipe diameter ($m$), pipe roughness ($m$), node elevation ($m$), and reservoir total head ($m$).
- **None = Not Set (No Invented Defaults)**: Unset parameters default to `None`. No arbitrary default numbers (e.g., standard pipe diameters or lengths) are ever invented or assumed.
- **Reservoir Head Semantics**: `head` represents the total hydraulic head of the water surface ($H_R$, in metres) and is valid only for reservoirs ($P_R = H_R - z$, where $z$ is elevation). Attempting to set `head` on junctions or tanks raises `ValueError`.
- **Legacy Node Elevations as Placeholders**: v1.0 files stored default elevations of `50.0 m` on all nodes. These numbers serve as structural placeholders rather than true surveyed data.
- **Roughness Interpretation**: Pipe roughness specifies absolute equivalent sand roughness ($\varepsilon$, in metres) for Darcy-Weisbach calculations, not dimensionless coefficients.
- **Backward Compatibility and Schema Evolution**: Format version 2 extends `.wnet` to persist physical parameters while preserving full backward compatibility with version 1 files. Unknown keys in node, pipe, or top-level objects are ignored during deserialization to maintain forward resilience.

---

## 11. UI Physical Parameter Entry and Properties Editor

- **Empty Field = Not Set (`None`)**: In the Add Node/Pipe forms and the Properties editor, an empty text field denotes an unset parameter (`None`). Clearing a value and pressing Apply unsets the parameter in the model.
- **Pump Toggle Not Editable After Creation**: A pipe cannot be switched between pumped and non-pumped in the Properties editor. The `has_pump` flag is fixed upon creation; if `has_pump` is true, its power rating can be adjusted in the Properties editor.
- **Tank Capacity Stored Only**: Tank `capacity` is editable in the Properties editor with a tooltip noting it is stored for reference and not yet incorporated into DAE matrix equations.
- **Input Fields Retained on Add**: Values in the Add Node and Add Pipe forms remain populated after clicking "Add" so users can rapidly add multiple network elements with matching properties without retyping.

---

## 12. Qt GraphicsScene Graph View

- **Native Qt Graphics Architecture**: Replaced Matplotlib canvas with native `QGraphicsScene` / `QGraphicsView` for network rendering, eliminating Matplotlib redraw latency, layout resets, and thread/context switching overhead while preserving Matplotlib in the project dependencies for other potential consumers.
- **Coordinate System Mapping**: Network models use Cartesian coordinates in `[-1.0, 1.0]` with $+Y$ pointing upward. The Qt scene uses computer graphics convention where $+Y$ points downward. Conversion is defined by $x_{scene} = x_{model} \times \text{SCALE}$ and $y_{scene} = -y_{model} \times \text{SCALE}$, with fixed $\text{SCALE} = 300.0$.
- **Edge Geometry & Curvature Separation**: Pipes stop cleanly at the node circular boundary rather than intersecting node centers. Parallel edges between identical endpoints are separated via quadratic Bezier curves with opposing lateral curvature offsets ($\pm 0.25$) to prevent visual overlap.
- **Fixed-Size Legend & Overlay Elements**: Node type legend is implemented with `QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations` and pinned to the viewport top-right so it remains readable and stationary under zoom and pan operations.
- **Zoom & Pan Stability**: Viewport transformations persist across property edits and network refreshes; automatic recentering is triggered only on project load or explicit user click on the "Fit" button.
- **Fit Quality & Margins**: Dynamic fit calculates usable viewport bounds excluding explicit margins (minimum 20 px padding from any viewport edge) and sets scene bounds tightly aligned with network contents to prevent center drift caused by untransformed UI overlays (such as the legend).

---

## 13. Interactive Node Dragging, Selection Sync, and Visual Styling

- **Dragging Marks Project Modified**: When a node is dragged with the mouse, `GraphView.positions_changed` is emitted once upon mouse release if and only if a real translation occurred. MainWindow connects this signal to mark the project modified (displaying window title asterisk and triggering the save prompt on close/new). Programmatic positioning (such as loading a file or example) does not mark the project modified.
- **Re-layout Discards Custom Positions**: Clicking "Re-layout" recalculates automatic spring layout coordinates for all nodes and marks the project modified.
- **Live Pipe Following & Curvature Preservation**: While dragging a node, attached pipes, arrowheads, and labels update live at 60 FPS using an adjacency map (`_node_pipes`). Parallel pipes maintain their opposing curvature offsets throughout dragging.
- **Live Internal Position Sync**: The internal `_pos` dictionary in model coordinates is kept in sync during dragging, ensuring that background refreshes (such as editing pipe parameters in Properties) never reset or discard dragged coordinates.
- **Selection Visual Distinction & Dual Styling**:
  - Blue selection ring / thicker stroke (`#0078D7`, 3.5–4.0 px) indicates the active element selected in the table or canvas.
  - Red outline (`#FF0000`, 3.0–3.5 px) indicates warnings highlighted by the Checks tab.
  - When an element is simultaneously selected and highlighted, dual concentric rings (outer blue ring at radius 24, inner red ring at radius 20) or stacked strokes ensure both states are independently distinguishable.
- **Empty Canvas Click Clears Selection**: Clicking empty canvas background clears both table selection and graph selection without modifying the network. Panning the view does not clear selection.
- **Tooltip Formatting & Metric Units**: Hover tooltips show physical quantities in standard metric units (`m` for length/elevation/head/diameter/roughness, `kW` for pump power) and explicitly display `"not set"` for `None` values. Reservoir total head is displayed only for reservoirs.



