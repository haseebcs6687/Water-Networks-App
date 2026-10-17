# Changelog

All notable changes to the Water Network Modeler application will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- **Plot Readability & Formatting (`ui/comparison_plots.py`)**:
  - Enforced minimum visible panel span rules: pressure and total head panels auto-scaled with a minimum span of $\max(0.5\% \cdot \max|y|, 0.01\text{ m})$ centered symmetrically around the midpoint, preventing misleading separation of micro-difference curves.
  - Global flow scaling enforcing $1\%$ of largest flow across panels, with fixed $[-10^{-3}, 10^{-3}]\text{ m}^3/\text{s}$ window for all-zero flow series.
  - Custom tick formatter (`make_tick_formatter`) displaying $\le 4$ decimal places with standard decimal notation (no scientific offset) and hiding extraneous ticks outside panel boundaries.
  - Strict constrained figure layout with `fig.align_ylabels()` and dynamic margin reservations preventing any text or label clipping across all window sizes (1900x900, 1100x800, 640x820, and 200 DPI export).
- **Responsive Layout & Small Windows (`ui/comparison_plots.py`, `ui/comparison_tab.py`)**:
  - Comparison plot canvas embedded in `QScrollArea` with a minimum figure size of $640 \times 820$ px (`min_h = max(820, n * 120)`), allowing smooth scrolling instead of compression on small screens.
  - Responsive legend placement: automatically relocates above the first panel (`loc='lower center'`, `ncol=2`) when canvas width $< 800$ px.
  - "Hide setup" / "Show setup" toggle button on collapsible left splitter handle to instantly maximize plot area.
- **Outdated Warning Banner (`ui/comparison_tab.py`, `core/comparison.py`)**:
  - Pure signature-based verification using rounded physics parameters, eliminating false positives and ensuring immediate update on parameter edits, preset switches, and runs.
- **Graph View Legend Clearance & Example Layout (`ui/graph_view.py`, `core/examples.py`)**:
  - Fitted view automatically reserves a 136 px right margin for the pinned legend while keeping model content horizontally centered.
  - Exported PNG images place legend cleanly outside bounding box to guarantee zero overlap with nodes, pipes, and labels.
  - Re-spaced broken example network layout achieving distance ratio of 3.23 ($\le 6$) and minimum node distance of 0.50 model units.
- **Selftest Watchdog & Dialog Bypass (`main.py`)**:
  - Added 90-second `faulthandler.dump_traceback_later` watchdog with clean cancellation on success.
  - Bypassed all modal dialogs (`QMessageBox`, `QFileDialog`, `QDialog`) during `--selftest` execution.

  - Comparison tab refactored with a horizontal `QSplitter` dividing the setup column (minimum width $\ge 430$ px) and the results area.
  - Results area featuring full-width non-elided outdated warning banner and a 5-tab `QTabWidget`: "Plots", "Differences", "Equilibrium", "Dirac impulses", and "Parameters used".
  - High-fidelity reproduction of MATLAB reference `comparisonFigure` with stacked panels, shared time axis, solid `#0072B2` DAE curves per mode interval, stepped `#D91A1A` EPANET trajectories, switch jump indicators, and vertical switch event guidelines.
  - Dirac impulse indicators drawn with directed arrows ($h = 0.5 \times \text{range} \times \text{sign}(\text{coeff})$) and bold annotations with switch time and coefficients.
  - Option bar with configurable state checklist (including "MATLAB five", "All flows", "All" presets), Pressure head vs Total head (EPANET Head) elevation shift toggle, and Dirac arrows toggle with instant redraw from cached result.
  - Differences tab displaying linearly interpolated DAE samples compared directly against EPANET report times, formatted with 6 significant digits and clipboard copy (Ctrl+C).
  - Export capabilities: high-res 200 DPI figure save (PNG/PDF/SVG), full simulation timeseries CSV export with auxiliary impulses CSV, and verbatim snapshot EPANET `.inp` file export.
- **Comparison with EPANET Tab (`ui/comparison_tab.py`)**:
  - Dedicated 5th tab titled "Comparison with EPANET" placed immediately following existing views.
  - Live "Ready?" status box with green "Ready to compare" or red plain-language blocking problem bullet points updating on every change.
  - Interactive "Valves" table configuring valves at pipe start and end boundaries, with pump pipes safely disabled.
  - Scenario configuration editor with presets for MATLAB specimens 1 to 5, explicit $V_1/V_2$ valve mapping indicators, whole-second switching event tables with Add/Remove buttons, and end time controls.
  - Physics settings supporting Constant friction factor, Swamee-Jain, and Darcy-Weisbach models, with collapsed advanced controls for gravity $g$ and kinematic viscosity $\nu$.
  - Thread-safe background execution in worker `QThread` with progress bar, responsive UI, disablement against double-clicks, and safe application shutdown.
  - Comprehensive results presentation: Parameters used table, Equilibrium comparison table with DAE vs EPANET deltas and maximum differences summary, and Dirac impulses table displaying impulse coefficients alongside "EPANET: none".
  - Outdated warning banner ("Network or settings changed since this result - run again") appearing whenever changes invalidate prior results.
- **Interactive Valve Symbols & Graph Visualization (`ui/graph_view.py`)**:
  - Bow-tie valve symbols rendered at pipe boundaries where valves exist, tracking node movement and live pipe bending curves.
  - Non-interfering hit-testing forwarding selection to the parent pipe, informative tooltips, inclusion in exported images, and "Valve" entry in the pinned legend.
- **Project Persistence & Examples (`core/io.py`, `core/examples.py`, `ui/main_window.py`)**:
  - Full `.wnet` v2 persistence for valve flags, scenarios, and physics settings while maintaining full backward compatibility with v1 and v2 files lacking scenarios.
  - New menu entry `File > Load Example > Specimen with valves (EPANET comparison)` loading the 3-node, 2-pipe specimen network with valves and scenario 1.
- **Comparison Coordinator (`core/comparison.py`)**:
  - `problems()` check, `parameters_table()` generator, and `run_comparison()` executing on isolated network snapshots with SHA-256 signature tracking.
  - Direct execution of the official EPANET 2.3.5 / 2.2+ engine via standard `ctypes` on standalone `core/lib/epanet2.dll` (MIT License / Public Domain).
  - Project handle API lifecycle (`EN_createproject`, `EN_open`, `EN_openH`, `EN_initH`, `EN_runH`, `EN_nextH`, `EN_closeH`, `EN_close`, `EN_deleteproject`) ensuring thread-safe execution in worker threads with zero state leaks.
  - Generates `EpanetResult` containing simulation times, state trajectories `X` formatted in identical column ordering to the DAE solver (flows, then pressure heads), state labels, engine version, input text, and translated warning strings.
- **Generic EPANET Export (`core/epanet_export.py`)**:
  - `write_inp` and `export_epanet` generating EPANET 2.2 input files (`.inp`) with SI metric units (`Units CMS`, `Headloss D-W`), viscosity from `PhysicsSettings.nu`, duration from scenario `t_end`, and 1-second hydraulic/report timesteps.
  - Reproduces the MATLAB reference network layout: lossless connector pipes for reservoir state capture, TCV valves with setting 0 / loss 0 for pipe valves with intermediate `<pipe>_L` and `<pipe>_R` junctions, and 1 cm stub pipes with minor losses $K = f L / D$ for constant friction mode.
  - Comprehensive `ExportMap` bidirectional mapping between DAE state vector labels and EPANET link/node elements.
  - Whole-second switch time validation rejecting sub-second switching with readable `ScenarioError`.
- **Standalone PyInstaller Packaging Proof**:
  - Executable includes `epanet2.dll` and verified to run 100% offline in isolated environments with cleaned PATH (no Python runtime or administrative rights required).
  - Extended `--selftest` with automated real EPANET engine execution on specimen scenario 2.
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
