"""ui/comparison_plots.py – Matplotlib-based comparison plot widget reproducing MATLAB comparisonFigure.

Includes:
- draw_comparison(fig, result, options)
- ComparisonPlots widget with navigation toolbar and export buttons
- Options bar: States dropdown checklist, Pressure vs Total head, Show Dirac arrows
- Export actions: Save figure (PNG/PDF/SVG), Export data (CSV), Export EPANET input (.inp)
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QAction, QKeySequence
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QMenu,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QFrame,
)

import matplotlib
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.lines import Line2D
from matplotlib.ticker import ScalarFormatter, FuncFormatter

from core.comparison import ComparisonResult
from core.plotdata import (
    default_states,
    series,
    decimate_series,
    impulse_arrows,
    engine_label,
)


def apply_panel_span_rules(
    current_ymin: float,
    current_ymax: float,
    panel_max_abs_y: float,
    is_flow: bool,
    global_max_abs_flow: float,
) -> Tuple[float, float]:
    """Calculate widened (ymin, ymax) limits according to Step 1a rules."""
    span = current_ymax - current_ymin
    ymid = (current_ymin + current_ymax) / 2.0
    if is_flow:
        if global_max_abs_flow == 0.0:
            return (-0.001, 0.001)
        else:
            target_span = 0.01 * global_max_abs_flow
            if span < target_span:
                return (ymid - target_span / 2.0, ymid + target_span / 2.0)
    else:
        target_span = max(0.005 * panel_max_abs_y, 0.01)
        if span < target_span:
            return (ymid - target_span / 2.0, ymid + target_span / 2.0)
    return (current_ymin, current_ymax)


_apply_panel_span_rules = apply_panel_span_rules


def make_tick_formatter(get_limits_fn):
    """Return a FuncFormatter that prints at most 4 decimals, no scientific offset,
    and returns empty string for ticks outside the axis limits."""
    def _format(val, pos=None):
        lims = get_limits_fn()
        if lims is not None:
            if val < lims[0] - 1e-6 or val > lims[1] + 1e-6:
                return ""
        if abs(val) < 1e-12:
            return "0"
        s = f"{val:.4f}".rstrip("0").rstrip(".")
        if s == "-0" or s == "":
            return "0"
        return s

    return FuncFormatter(_format)


def draw_comparison(
    fig: Figure,
    result: Optional[ComparisonResult],
    options: Optional[Dict[str, Any]] = None,
):
    """Draw stacked comparison figure faithfully reproducing MATLAB's comparisonFigure.

    Parameters
    ----------
    fig : matplotlib.figure.Figure
        The target figure to draw on.
    result : ComparisonResult, optional
        Simulation comparison result.
    options : dict, optional
        Display options:
        - 'selected_states': list of state labels to show
        - 'head_mode': 'pressure' or 'total'
        - 'show_dirac': bool (default True)
        - 'title': optional scenario title
    """
    fig.clear()
    fig.patch.set_facecolor("white")
    fig.set_layout_engine("constrained")

    if result is None:
        ax = fig.add_subplot(111)
        ax.set_facecolor("white")
        ax.text(
            0.5,
            0.5,
            "Run comparison to display plots.",
            horizontalalignment="center",
            verticalalignment="center",
            transform=ax.transAxes,
            color="#888888",
            fontsize=12,
            fontstyle="italic",
        )
        ax.axis("off")
        fig.canvas.draw_idle()
        return

    opts = options or {}
    selected = opts.get("selected_states")
    if not selected:
        selected = default_states(result)
    head_mode = opts.get("head_mode", "pressure")
    show_dirac = opts.get("show_dirac", True)

    n_panels = len(selected)
    if n_panels == 0:
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, "No states selected.", ha="center", va="center", color="#888888")
        ax.axis("off")
        fig.canvas.draw_idle()
        return

    # Palette matching MATLAB comparisonFigure
    # DAE: (0, 0.447, 0.698) = #0072B2
    # EPANET: (0.85, 0.10, 0.10) = #D91A1A
    # Grid: alpha 0.12, switch line: #CCCCCC
    cD = (0.0, 0.447, 0.698)
    cE = (0.85, 0.10, 0.10)
    cSwitch = "#CCCCCC"

    T = float(result.scenario.t_end)
    xlims = (-0.01 * T, T)

    # Check if network is the specimen network
    is_specimen = (
        len(result.snapshot.pipes) == 2
        and all(s in result.dae.labels for s in ["Pipe_1_Flow", "Pipe_2_Flow", "Pipe_1_R", "Pipe_2_L", "Pipe_2_R"])
    )

    specimen_labels = {
        "Pipe_1_Flow": "x1 = Q1 [m³/s]",
        "Pipe_2_Flow": "x2 = Q2 [m³/s]",
        "Pipe_1_R": "x5 pipe-1 end [m]",
        "Pipe_2_L": "x4 d/s of V1 [m]",
        "Pipe_2_R": "x6 pipe-2 end [m]",
    }

    # Precompute Dirac impulses
    all_imp_arrows = impulse_arrows(result, selected) if show_dirac else {lbl: [] for lbl in selected}

    # Step 1a: compute global maximum |flow| over all displayed flow series
    global_max_flow = 0.0
    for lbl in selected:
        if "Flow" in lbl:
            d_segs, _, ep_data = series(result, lbl, kind=head_mode)
            for _, yk in d_segs:
                if len(yk) > 0:
                    global_max_flow = max(global_max_flow, float(np.max(np.abs(yk))))
            t_ep, y_ep = ep_data
            if len(y_ep) > 0:
                global_max_flow = max(global_max_flow, float(np.max(np.abs(y_ep))))

    axes = fig.subplots(nrows=n_panels, ncols=1, sharex=True, squeeze=False)[:, 0]

    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance()
    if _app is not None:
        _app.processEvents()

    for r, lbl in enumerate(selected):
        if _app is not None:
            _app.processEvents()

        ax = axes[r]
        ax.set_facecolor("white")
        ax.grid(True, alpha=0.12, color="gray", linestyle="-")
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("#333333")

        ax.set_xlim(xlims)

        # Step 1a: Tick formatter with at most 4 decimals, no offset, pruning outside ticks
        ax.yaxis.set_major_formatter(make_tick_formatter(ax.get_ylim))

        dae_segs, jumps, ep_data = series(result, lbl, kind=head_mode)

        # 1. DAE segments (one per mode, solid line, decimated to <= 4000 pts for drawing only)
        for tk, yk in dae_segs:
            t_plot, y_plot = decimate_series(tk, yk, max_points=4000)
            ax.plot(t_plot, y_plot, "-", color=cD, linewidth=1.6)

        # 2. Dotted jump line and vertical switch line
        for ts, y_before, y_after in jumps:
            ax.plot([ts, ts], [y_before, y_after], ":", color=cD, linewidth=1.5)
            ax.axvline(x=ts, color=cSwitch, linestyle="-", linewidth=1.0, zorder=1)

        # In scenarios with switches where jump is 0 (or no flow jump), still draw switch line
        if result.scenario.events and not jumps:
            for ev in result.scenario.events:
                ax.axvline(x=ev.time, color=cSwitch, linestyle="-", linewidth=1.0, zorder=1)

        # 3. EPANET step plot on top
        t_ep, y_ep = ep_data
        ax.plot(t_ep, y_ep, "-", color=cE, linewidth=0.9, drawstyle="steps-post", zorder=4)

        # 4. Y-axis label
        if is_specimen and lbl in specimen_labels:
            ylab = specimen_labels[lbl]
            if head_mode == "total" and "[m]" in ylab:
                ylab = ylab.replace("[m]", "total head [m]")
        else:
            if "Flow" in lbl:
                ylab = f"{lbl}  Q [m³/s]"
            else:
                ylab = f"{lbl}  {'total head [m]' if head_mode == 'total' else 'pressure head [m]'}"
        ax.set_ylabel(ylab, fontsize=9)

        # 5. Dirac arrows
        yl = ax.get_ylim()
        arrows = all_imp_arrows.get(lbl, [])
        if arrows:
            for ts, coeff, base in arrows:
                yrange = yl[1] - yl[0]
                if abs(yrange) < 1e-9:
                    yrange = 1.0
                h = 0.5 * yrange * (1.0 if coeff > 0 else -1.0)
                marker = "^" if coeff > 0 else "v"

                # Solid arrow stem
                ax.plot([ts, ts], [base, base + h], "-", color=cD, linewidth=2.2, zorder=6)
                # Triangle marker
                ax.plot(
                    ts,
                    base + h,
                    marker=marker,
                    color=cD,
                    markerfacecolor=cD,
                    markersize=7,
                    zorder=7,
                )
                # Text label
                sign_str = f"{coeff:+.2f}"
                txt = f"DAE: Dirac {sign_str} δ(t - {ts:g})\nEPANET: none"
                ax.text(
                    ts + 0.03 * T,
                    base + 0.62 * h,
                    txt,
                    color=cD,
                    fontsize=8.5,
                    fontweight="bold",
                    verticalalignment="center",
                    bbox=dict(
                        boxstyle="square,pad=0.25",
                        facecolor="white",
                        edgecolor="none",
                        alpha=0.95,
                    ),
                    zorder=8,
                )
                # Extend y limits
                new_ymin = min(yl[0], base + 1.35 * min(0.0, h))
                new_ymax = max(yl[1], base + 1.35 * max(0.0, h))
                ax.set_ylim(new_ymin, new_ymax)
        else:
            ax.set_ylim(yl)

        # Step 1a: Minimum visible range rule
        ymin, ymax = ax.get_ylim()
        is_flow = ("Flow" in lbl)
        max_abs_y = max(abs(ymin), abs(ymax))
        new_ymin, new_ymax = apply_panel_span_rules(ymin, ymax, max_abs_y, is_flow, global_max_flow)
        ax.set_ylim(new_ymin, new_ymax)

        # Top panel: title and legend
        if r == 0:
            title_text = opts.get("title") or "switched DAE  and EPANET"
            ax.set_title(title_text, fontsize=10)

            line_dae = Line2D([0], [0], color=cD, linewidth=1.6)
            line_ep = Line2D([0], [0], color=cE, linewidth=0.9)

            fig_w = fig.bbox.width
            if fig_w < 800:
                ax.legend(
                    [line_dae, line_ep],
                    ["switched DAE", engine_label(result)],
                    loc="lower center",
                    bbox_to_anchor=(0.5, 1.05),
                    ncol=2,
                    frameon=False,
                    fontsize=8,
                )
            else:
                ax.legend(
                    [line_dae, line_ep],
                    ["switched DAE", engine_label(result)],
                    loc="center left",
                    bbox_to_anchor=(1.02, 0.5),
                    frameon=False,
                    fontsize=8,
                )

        # Bottom panel: x axis label and formatter
        if r == n_panels - 1:
            ax.xaxis.set_major_formatter(make_tick_formatter(ax.get_xlim))
            ax.set_xlabel("t [s]", fontsize=10)

    fig.align_ylabels()
    fig.canvas.draw_idle()


class ComparisonPlots(QWidget):
    """Widget containing comparison plot canvas, options bar, and export buttons."""

    status_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._result: Optional[ComparisonResult] = None
        self._selected_states: List[str] = []
        self._head_mode: str = "pressure"
        self._show_dirac: bool = True

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # -------------------------------------------------------------
        # TOP OPTIONS BAR
        # -------------------------------------------------------------
        opt_bar = QHBoxLayout()
        opt_bar.setSpacing(12)

        # 1. States dropdown checklist
        self.states_btn = QToolButton()
        self.states_btn.setText("States...")
        self.states_btn.setPopupMode(QToolButton.InstantPopup)
        self.states_menu = QMenu(self)
        self.states_btn.setMenu(self.states_menu)
        opt_bar.addWidget(self.states_btn)

        # 2. Head mode radio buttons
        opt_bar.addWidget(QLabel("Display:"))
        self.radio_group = QButtonGroup(self)
        self.radio_pressure = QRadioButton("Pressure head")
        self.radio_pressure.setChecked(True)
        self.radio_total = QRadioButton("Total head (EPANET Head)")
        self.radio_group.addButton(self.radio_pressure, 0)
        self.radio_group.addButton(self.radio_total, 1)
        self.radio_group.buttonClicked.connect(self._on_head_mode_changed)
        opt_bar.addWidget(self.radio_pressure)
        opt_bar.addWidget(self.radio_total)

        # 3. Show Dirac arrows checkbox
        self.dirac_check = QCheckBox("Show Dirac arrows")
        self.dirac_check.setChecked(True)
        self.dirac_check.toggled.connect(self._on_dirac_toggled)
        opt_bar.addWidget(self.dirac_check)

        opt_bar.addStretch()
        layout.addLayout(opt_bar)

        # -------------------------------------------------------------
        # MATPLOTLIB CANVAS & TOOLBAR (In QScrollArea)
        # -------------------------------------------------------------
        self.fig = Figure(figsize=(7, 9), facecolor="white", layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("background-color: #FFFFFF; border: 1px solid #DDDDDD;")

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.canvas.setMinimumSize(640, 820)
        self.scroll_area.setWidget(self.canvas)

        layout.addWidget(self.toolbar)
        layout.addWidget(self.scroll_area, 1)

        # -------------------------------------------------------------
        # BOTTOM EXPORT BUTTONS BAR
        # -------------------------------------------------------------
        export_bar = QHBoxLayout()
        export_bar.setSpacing(10)

        self.save_fig_btn = QPushButton("Save figure...")
        self.save_fig_btn.setToolTip("Save high-resolution plot (PNG 200 dpi, PDF, SVG)")
        self.save_fig_btn.clicked.connect(self.save_figure_action)
        export_bar.addWidget(self.save_fig_btn)

        self.export_csv_btn = QPushButton("Export data (CSV)...")
        self.export_csv_btn.setToolTip("Export comparison time series and Dirac impulses as CSV")
        self.export_csv_btn.clicked.connect(self.export_csv_action)
        export_bar.addWidget(self.export_csv_btn)

        self.export_inp_btn = QPushButton("Export EPANET input file (.inp)...")
        self.export_inp_btn.setToolTip("Export the exact EPANET input file used in this simulation")
        self.export_inp_btn.clicked.connect(self.export_inp_action)
        export_bar.addWidget(self.export_inp_btn)

        export_bar.addStretch()
        layout.addLayout(export_bar)

        self.clear()

    # -----------------------------------------------------------------
    # State & Redraw logic
    # -----------------------------------------------------------------

    def set_result(self, result: Optional[ComparisonResult]):
        """Store result and redraw comparison plot."""
        self._result = result
        if result is not None:
            self._selected_states = default_states(result)
            self._build_states_menu()
        else:
            self._selected_states = []
            self.states_menu.clear()

        self.redraw()

    def clear(self):
        """Clear the plot canvas and reset state."""
        self._result = None
        self._selected_states = []
        self.states_menu.clear()
        draw_comparison(self.fig, None)

    def redraw(self):
        """Redraw plot using stored result and current options (no re-simulation)."""
        n = len(self._selected_states) if self._selected_states else 5
        min_h = max(820, n * 120)
        self.canvas.setMinimumSize(640, min_h)
        opts = {
            "selected_states": list(self._selected_states),
            "head_mode": self._head_mode,
            "show_dirac": self._show_dirac,
        }
        draw_comparison(self.fig, self._result, opts)

    def _build_states_menu(self):
        """Populate the States dropdown checklist with actions."""
        self.states_menu.clear()
        if self._result is None:
            return

        all_states = list(self._result.dae.labels)

        # Quick actions
        act_matlab = self.states_menu.addAction("MATLAB five")
        act_matlab.triggered.connect(self._select_matlab_five)

        act_flows = self.states_menu.addAction("All flows")
        act_flows.triggered.connect(self._select_all_flows)

        act_all = self.states_menu.addAction("All states")
        act_all.triggered.connect(self._select_all_states)

        self.states_menu.addSeparator()

        self._state_actions: Dict[str, QAction] = {}
        for s in all_states:
            act = QAction(s, self.states_menu)
            act.setCheckable(True)
            act.setChecked(s in self._selected_states)
            act.toggled.connect(lambda chk, state=s: self._on_state_toggled(state, chk))
            self.states_menu.addAction(act)
            self._state_actions[s] = act

    def _on_state_toggled(self, state: str, checked: bool):
        if checked and state not in self._selected_states:
            self._selected_states.append(state)
        elif not checked and state in self._selected_states:
            self._selected_states.remove(state)
        self.redraw()

    def _select_matlab_five(self):
        if self._result is None:
            return
        m5 = ["Pipe_1_Flow", "Pipe_2_Flow", "Pipe_1_R", "Pipe_2_L", "Pipe_2_R"]
        self._selected_states = [s for s in m5 if s in self._result.dae.labels]
        self._update_menu_checkboxes()
        self.redraw()

    def _select_all_flows(self):
        if self._result is None:
            return
        self._selected_states = [s for s in self._result.dae.labels if "Flow" in s]
        self._update_menu_checkboxes()
        self.redraw()

    def _select_all_states(self):
        if self._result is None:
            return
        self._selected_states = list(self._result.dae.labels)
        self._update_menu_checkboxes()
        self.redraw()

    def _update_menu_checkboxes(self):
        if hasattr(self, "_state_actions"):
            for s, act in self._state_actions.items():
                act.blockSignals(True)
                act.setChecked(s in self._selected_states)
                act.blockSignals(False)

    def _on_head_mode_changed(self):
        self._head_mode = "total" if self.radio_total.isChecked() else "pressure"
        self.redraw()

    def _on_dirac_toggled(self, checked: bool):
        self._show_dirac = checked
        self.redraw()

    # -----------------------------------------------------------------
    # Export Actions
    # -----------------------------------------------------------------

    def save_figure_action(self):
        """Export high-resolution comparison plot to PNG, PDF, or SVG."""
        if self._result is None:
            QMessageBox.information(self, "No Results", "Run a comparison first to export the plot.")
            return

        default_name = f"comparison_{self._default_filename_slug()}.png"
        path_str, sel_filter = QFileDialog.getSaveFileName(
            self,
            "Save Comparison Figure",
            default_name,
            "PNG Images (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*.*)",
        )
        if not path_str:
            return

        try:
            path = Path(path_str)
            dpi = 200 if path.suffix.lower() == ".png" else "figure"
            self.fig.savefig(
                path,
                dpi=dpi,
                facecolor="white",
                edgecolor="none",
                bbox_inches="tight",
            )
            msg = f"Saved figure to {path.name}"
            self.status_message.emit(msg)
        except Exception as e:
            QMessageBox.critical(self, "Save Figure Error", f"Failed to save figure: {e}")

    def export_csv_action(self):
        """Export time-series comparison data and Dirac impulses as CSV."""
        if self._result is None:
            QMessageBox.information(self, "No Results", "Run a comparison first to export data.")
            return

        default_name = f"comparison_{self._default_filename_slug()}.csv"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Comparison Data (CSV)",
            default_name,
            "CSV Files (*.csv);;All Files (*.*)",
        )
        if not path_str:
            return

        try:
            main_path = Path(path_str)
            self._write_csv_data(main_path)

            # Secondary impulses file: <name>_impulses.csv
            stem = main_path.stem
            imp_path = main_path.parent / f"{stem}_impulses.csv"
            self._write_csv_impulses(imp_path)

            msg = f"Exported comparison CSV and impulses to {main_path.name}"
            self.status_message.emit(msg)
        except Exception as e:
            QMessageBox.critical(self, "Export CSV Error", f"Failed to export CSV: {e}")

    def _write_csv_data(self, path: Path):
        """Write time, DAE, EPANET, diff columns sampled at EPANET report times."""
        res = self._result
        assert res is not None

        from core.plotdata import _strictly_increasing_dae_time_series
        tall, Xall = _strictly_increasing_dae_time_series(res)
        te = res.epanet.t

        states = list(res.dae.labels)
        header = ["time"]
        for s in states:
            header.extend([f"{s}_DAE", f"{s}_EPANET", f"{s}_diff"])

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for k, t_val in enumerate(te):
                row = [f"{t_val:.6f}"]
                for col_idx, s in enumerate(states):
                    dae_val = float(np.interp(t_val, tall, Xall[:, col_idx]))
                    ep_val = float(res.epanet.series(s)[k])
                    diff_val = dae_val - ep_val
                    row.extend([f"{dae_val:.6f}", f"{ep_val:.6f}", f"{diff_val:.6f}"])
                writer.writerow(row)

    def _write_csv_impulses(self, path: Path):
        """Write impulse records to CSV."""
        res = self._result
        assert res is not None

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time", "state", "coefficient"])
            for imp in res.dae.impulses:
                for idx, lbl in enumerate(res.dae.labels):
                    coeff = float(imp.coefficients[idx])
                    if abs(coeff) > 1e-9:
                        writer.writerow([f"{imp.time:.6f}", lbl, f"{coeff:.6f}"])

    def export_inp_action(self):
        """Export the exact EPANET input file used in this run."""
        if self._result is None:
            QMessageBox.information(self, "No Results", "Run a comparison first to export the .inp file.")
            return

        default_name = f"comparison_{self._default_filename_slug()}.inp"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export EPANET Input File",
            default_name,
            "EPANET Input Files (*.inp);;All Files (*.*)",
        )
        if not path_str:
            return

        try:
            inp_text = getattr(self._result.epanet, "inp_text", None)
            if not inp_text:
                from core.epanet_export import export_epanet
                inp_text = export_epanet(
                    self._result.snapshot,
                    self._result.scenario,
                    self._result.settings,
                )

            with open(path_str, "w", encoding="utf-8") as f:
                f.write(inp_text)

            msg = f"Exported EPANET input file to {Path(path_str).name}"
            self.status_message.emit(msg)
        except Exception as e:
            QMessageBox.critical(self, "Export INP Error", f"Failed to export EPANET .inp file: {e}")

    def _default_filename_slug(self) -> str:
        if self._result and self._result.scenario and self._result.scenario.title:
            slug = self._result.scenario.title.lower().replace(" ", "_")
            # Keep alphanumeric and underscores
            cleaned = "".join(c for c in slug if c.isalnum() or c == "_")
            if "specimen_1" in cleaned or "valve_1_closed" in cleaned:
                return "scenario1"
            return cleaned[:25] or "run"
        return "run"
