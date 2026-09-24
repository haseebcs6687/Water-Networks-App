# Water Network Modeler (Desktop)

A Windows desktop application for building and analysing water distribution
networks, converted from an earlier Streamlit web app. Built with
**PySide6**, **NetworkX**, **NumPy** and **Matplotlib**, and grounded in a
research paper on the graph-theoretic and switched-DAE modelling of water
networks.

## Features

- Build a network interactively: add junctions, tanks and reservoirs; connect
  them with pipes and pumps.
- Directed network graph with pump edges shown separately.
- Symbolic **E, A, F, G** matrices of the underlying DAE model
  `E x' = A x + f + g(x)`, with LaTeX and CSV export.
- **Incidence matrices**: full `I(G)`, reduced `I^r(G)`, modified `I^m(G)`,
  and pipe pressure differences `ΔP = Iᵀ P`.
- **Checks tab**: numeric regularity test of the matrix pencil `(E, A)`, plus
  plain-language validation (every connected component must reach a supply
  node; pumps must not form a loop, including pumps in series between two
  supplies).
- Save/open projects as `.wnet` (JSON) files, with two bundled example
  networks.
- Packaged as a self-contained Windows executable (PyInstaller) — no Python
  installation required to run it.

## Project layout

```
core/       Pure calculation logic: network model, matrix construction,
            regularity checks, incidence matrices, save/load. No UI code.
ui/         PySide6 desktop interface (Network / Matrices / Incidence /
            Checks tabs). Imports only from core/.
tests/      Pytest suite (unit tests for core/, offscreen smoke tests for ui/).
legacy/     The original Streamlit web app, kept for reference. Not used by
            the desktop app.
tools/      Icon generation script.
assets/     App icon.
main.py     Desktop app entry point.
```

## Running from source

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\python main.py
```

Run the tests with:

```powershell
.\.venv\Scripts\pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest -q
```

## Building the Windows executable

```powershell
.\.venv\Scripts\pip install -r requirements-dev.txt
.\build.ps1
```

This produces `dist/WaterNetworkModeler/WaterNetworkModeler.exe`. Prebuilt
binaries are not committed to this repository (they are large and
machine-specific) — see the project's Releases page instead, if published
there.

## Background

The matrix model follows the paper *"Water network as graph and its
solvability"*, which formulates a water distribution network as a directed
graph and studies the regularity of its switched differential-algebraic
equation model. `ASSUMPTIONS.md` documents every modelling choice made where
the paper was ambiguous (e.g. tank sign convention, treating tanks as supply
nodes for connectivity).

## Status

This is an early version. Valve/pump on-off switching, demand values, and
solving the DAE numerically are not yet implemented — see `ASSUMPTIONS.md`
and the "Not included yet" notes for details.

## License

Add a license of your choice (e.g. MIT) before making this repository public
long-term, or leave unlicensed if you don't want others to reuse the code.
