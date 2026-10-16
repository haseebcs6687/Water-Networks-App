# Changelog

All notable changes to the Water Network Modeler application will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Theorem 8 Switched DAE Solver (`core/dae_solver.py`)**:
  - Pure NumPy implementation of Wong sequences and modified quasi-Weierstrass form (QWF) decomposition into differential and algebraic subspaces.
  - Faithful SVD-based linear algebra helpers (`orthT`, `nullT`, `rnk`, `preimg`, `extendBasis`) with $10^{-10} \max(1, s_{\max})$ tolerance.
  - Mode analysis with diagnostic reporting matching MATLAB reference (`|det(E-A)|`, `||M*Eimp||`, `||N1w||`, `||M*T2w||`, `||N2||`, `eig(J)`).
  - Dirac impulse $\delta_{t_s}$ calculation for valve switching events via formula (10c) and independent cross-check against formula (6) of the paper ($x[t_s] = -E^{\text{imp}} x(t_s^-)$).
  - Consistent rest state calculation ($v = 0$, zero flows) for initial scenario state without artificial jumps or impulses.
  - Pure NumPy adaptive Dormand-Prince 5(4) integrator (`ode45` equivalent) with $rtol = 10^{-10}$, $atol = 10^{-12}$, maximum step $(t_1 - t_0)/200$, and dense Hermite interpolation on a uniform sampling grid (default 40 pts/s).
  - Simulation result object (`SimulationResult`) with series extractors, head converters, and switch-time duplicate sample recording ($t_s^-$ and $t_s^+$) for jump visualization.
- **Pipe Friction Formulations (`core/physics.py`)**:
  - `PhysicsSettings.friction_mode`: supports `"constant"` (default, $f = 0.02$), `"swamee_jain"`, and `"darcy_weisbach"`.
  - Swamee-Jain explicit turbulent approximation across all flow rates.
  - Darcy-Weisbach formulation following the EPANET 2.2 engine rule: Hagen-Poiseuille laminar flow ($64/\text{Re}$ with singularity-free linear term at $Q = 0$), Dunlop cubic interpolation in the transition zone ($2000 < \text{Re} < 4000$), and Swamee-Jain in the turbulent zone ($\text{Re} \ge 4000$).
  - Steady-state Newton-Raphson solver generalized to support nonlinear friction laws using numerical finite-difference Jacobian.

---

## [1.1.0] - 2026-10-17

### Added
- **Physical Parameters**: Support for entering and editing physical network properties in SI metric units:
  - Node elevation ($m$) for all node types.
  - Reservoir hydraulic head ($m$, valid only for reservoirs).
  - Pipe length ($m$), internal diameter ($m$), and absolute sand roughness ($\varepsilon$, $m$) stored for the planned comparison with EPANET.
  - Pump power rating ($kW$, stored for reference).
- **Properties Editor & Missing-Parameter Indicator**:
  - Interactive Properties panel in the build tab to view and edit properties of the selected node or pipe.
  - Live status indicator showing when all parameters are complete or reporting the exact count and list of missing parameters.
- **File Format Version 2 (.wnet v2)**:
  - Format version 2 persists physical network parameters, node coordinates, and custom pipe edge bends.
  - Full backward compatibility: v1 files load seamlessly with empty physical parameters defaulting to `None`.
  - Resilience against forward extensions: unknown JSON keys are safely ignored.
- **Native Qt Network Graph View**:
  - Replaced Matplotlib canvas with native Qt `QGraphicsScene` / `QGraphicsView` architecture for smooth, responsive 60 FPS rendering.
  - Fixed-size cosmetic node-type legend pinned to the viewport top-right that does not scale with zoom.
- **Interactive Node Dragging**:
  - Nodes can be moved freely across the canvas with the mouse.
  - Connected pipes, arrowheads, and labels follow node movement live in real time.
  - Moving a node marks the project modified.
- **Bidirectional Selection Sync**:
  - Selecting an element in the node or pipe table highlights it in the graph with a blue selection ring or line.
  - Clicking an element in the graph selects its row in the corresponding table and displays its properties in the Properties editor.
  - Clicking empty canvas background clears selection.
- **Interactive Tooltips**:
  - Hovering over nodes or pipes displays connection topology and physical properties in metric units (or `"not set"` when unset).
- **Bendable Pipes (Moving Edges)**:
  - Small cosmetic handle (visible on hover or when pipe is selected) at the midpoint of each pipe curve.
  - Dragging the handle or label bends the pipe live with real-time curve, arrowhead tangent, and label updates.
  - Double-clicking the handle resets the bend to automatic curvature.
  - Bend ratios are preserved across node dragging and saved in `.wnet` v2 files.
- **Fit to View & Cropped Image Export**:
  - One-click "Fit" button frames all network components with comfortable margins (centered on node bounds).
  - "Save image..." exports clean, cropped high-resolution PNG images on a white background with legend and margins.

### Fixed
- **Default elevation is unset**: Adding a node without an explicit elevation leaves elevation unset (`None`) instead of defaulting to 50.0.
- **Empty Fields = Not Set**: Unset parameters strictly default to `None` with no invented placeholder numbers; clearing a field and pressing Apply sets it back to `None`.
- **Stale Positions Between Examples**: Loading a new example or project clears existing positions cleanly so node positions do not carry over between distinct network topologies.
- **Bend Ratio Consistency**: Curvature and midpoint displacement are calculated relative to the chord connecting clipped node-boundary endpoints, ensuring exact mathematical agreement between perpendicular drag distance and rendered curve displacement.

---

## [1.0.0] - 2026-10-15

### Added
- Initial desktop release converted from Streamlit web application.
- Interactive network builder (junctions, tanks, reservoirs, pipes, pumps).
- Symbolic DAE matrices ($E, A, F, G$) with LaTeX and CSV export.
- Full, reduced, and modified incidence matrices ($I(G)$, $I^r(G)$, $I^m(G)$) and pressure difference vector ($\Delta P$).
- Matrix pencil regularity check and topological rule validation.
- Standalone self-contained Windows executable built with PyInstaller.
