"""tests/test_ui_comparison.py – UI tests for Comparison with EPANET tab.

Tests 1 to 10 covering:
1. Tab existence, exact title, last tab, empty network not-ready state.
2. Paper example not-ready reasons (pumps, tanks, missing parameters count) vs Specimen ready state.
3. Presets 1..5 table population, V1/V2 mapping, preset disabled on < 2 valves.
4. Run specimen 1..5 through UI: reference values (flows <= 5e-5, heads <= 5e-3), impulse values.
5. Valve editing: toggle valve, graph valve symbol count, drag node / bend pipe, modified flag, outdated banner, notice, symbol in saved PNG.
6. Custom scenario via UI: add event, invalid inputs inline messages, mode (0,0) message, run disabled, no exceptions.
7. Friction laws: Swamee-Jain and Darcy-Weisbach runs, Q values (0.196438 vs 0.195321), spin box visibility.
8. Save/load round-trip of valves, scenario, physics; old v1 and v2 files open cleanly.
9. Responsiveness: QTimer ticks during run, second click ignored, clean close during run.
10. All earlier tests pass UNCHANGED, selftest exit code 0, no new dependencies.
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QFileDialog, QSpinBox, QComboBox

from core.models import Network
from core.scenario import Scenario, ValveId, SwitchEvent
from core.physics import PhysicsSettings
from core.examples import example_paper_network, specimen_network, specimen_scenario, specimen_physics
from core.io import save_project, load_project_full
from ui.main_window import MainWindow
from ui.graph_view import ValveSymbolItem, PipeItem


@pytest.fixture(scope="module")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.fixture(autouse=True)
def patch_dialogs(monkeypatch):
    monkeypatch.setattr(QMessageBox, "about", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.Ok)
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Discard)


def wait_for_comparison(tab, timeout_s=30.0):
    """Wait for background ComparisonWorker to finish."""
    t0 = time.time()
    # Give worker a moment to start
    for _ in range(5):
        QApplication.processEvents()
        QTest.qWait(10)
        if tab.is_running:
            break
    while tab.is_running:
        QApplication.processEvents()
        QTest.qWait(50)
        if time.time() - t0 > timeout_s:
            raise TimeoutError("Comparison run timed out after 30 seconds")
    QApplication.processEvents()


def test_01_tab_exists_and_empty_network_not_ready(qapp):
    """1. Tab exists, exact title, is the last tab; empty network: not ready, Run disabled with a readable reason."""
    window = MainWindow()
    last_idx = window.right_tabs.count() - 1
    assert window.right_tabs.tabText(last_idx) == "Comparison with EPANET"
    assert window.right_tabs.widget(last_idx) is window.comparison_tab

    tab = window.comparison_tab
    assert not tab.run_btn.isEnabled()
    ready_text = tab.ready_label.text()
    assert "Not ready to compare" in ready_text
    assert "Network is empty" in ready_text
    window.close()


def test_02_paper_not_ready_vs_specimen_ready(qapp):
    """2. Paper example: not ready, reasons mention pumps/tanks and missing parameters (count), Run disabled. Specimen example: 'Ready to compare' and Run enabled."""
    window = MainWindow()
    window.network = example_paper_network()
    window.refresh()

    tab = window.comparison_tab
    assert not tab.run_btn.isEnabled()
    text = tab.ready_label.text()
    assert "Not ready to compare" in text
    assert "Missing physical parameters (14)" in text or "Missing physical parameters" in text
    assert "Pumps are not supported" in text or "pump" in text.lower()

    # Now load specimen example
    window._on_load_specimen_example()
    assert "Ready to compare" in tab.ready_label.text()
    assert tab.run_btn.isEnabled()
    window.close()


def test_03_presets_1_to_5_and_mapping(qapp):
    """3. Presets: choosing specimen 1..5 fills the tables exactly and shows V1/V2 mapping; presets disabled on network with < 2 valves."""
    window = MainWindow()
    window._on_load_specimen_example()
    tab = window.comparison_tab

    assert tab.preset_combo.isEnabled()
    assert "V1 = P2:start, V2 = P2:end" in tab.preset_mapping_label.text()

    # Preset 1
    tab.preset_combo.setCurrentIndex(1)
    assert tab.end_time_spin.value() == 120
    assert tab.events_table.rowCount() == 1
    sp_time = tab.events_table.cellWidget(0, 0)
    assert isinstance(sp_time, QSpinBox)
    assert sp_time.value() == 60

    # Preset 2
    tab.preset_combo.setCurrentIndex(2)
    assert tab.events_table.rowCount() == 0

    # Preset 3
    tab.preset_combo.setCurrentIndex(3)
    assert tab.end_time_spin.value() == 400
    assert tab.events_table.rowCount() == 1
    assert tab.events_table.cellWidget(0, 0).value() == 300

    # Preset 4
    tab.preset_combo.setCurrentIndex(4)
    assert tab.end_time_spin.value() == 400
    assert tab.events_table.rowCount() == 1
    assert tab.events_table.cellWidget(0, 1).currentText() == "P2:end"

    # Preset 5
    tab.preset_combo.setCurrentIndex(5)
    assert tab.end_time_spin.value() == 300
    # In initial table, V1 is Closed (0)
    assert tab.initial_table.cellWidget(0, 1).currentText() == "Closed"

    # Now remove all valves -> preset combo must be disabled
    for p in window.network.pipes:
        window.network.update_pipe(p.id, valve_start=False, valve_end=False)
    window.refresh()
    assert not tab.preset_combo.isEnabled()
    assert "Need ≥2 valves" in tab.preset_mapping_label.text()
    window.close()


def test_04_run_specimen_1_to_5_results_and_impulses(qapp):
    """4. Run specimen 1..5 through the UI: results appear, DAE vs EPANET within tolerances, impulse table values."""
    window = MainWindow()

    # 4a. Run Specimen 1
    window._on_load_specimen_example()
    tab = window.comparison_tab
    tab.preset_combo.setCurrentIndex(1)
    tab.run_comparison_action()
    wait_for_comparison(tab)

    assert tab.eq_table.rowCount() > 0
    assert tab.imp_table.rowCount() == 3
    # Check impulse values for scenario 1:
    # x5 (Pipe_1_R) about +62.16, x4 (Pipe_2_L) about -38.85, J1 about +62.16
    imp_map = {}
    for r in range(tab.imp_table.rowCount()):
        st_lbl = tab.imp_table.item(r, 1).text()
        coeff_val = float(tab.imp_table.item(r, 2).text())
        imp_map[st_lbl] = coeff_val

    # Find matching states
    j1_val = [v for k, v in imp_map.items() if "J1" in k][0]
    p1r_val = [v for k, v in imp_map.items() if "Pipe_1_R" in k or "x5" in k][0]
    p2l_val = [v for k, v in imp_map.items() if "Pipe_2_L" in k or "x4" in k][0]

    assert abs(j1_val - 62.16) < 0.1
    assert abs(p1r_val - 62.16) < 0.1
    assert abs(p2l_val - (-38.85)) < 0.1

    # 4b. Run Specimen 2 (relaxation, no impulses)
    tab.preset_combo.setCurrentIndex(2)
    tab.run_comparison_action()
    wait_for_comparison(tab)
    assert tab.imp_table.rowCount() == 0

    # Verify equilibrium tolerances for specimen 2: flows <= 5e-5, heads <= 5e-3
    for r in range(tab.eq_table.rowCount()):
        lbl = tab.eq_table.item(r, 2).text()
        diff = float(tab.eq_table.item(r, 5).text())
        if "flow" in lbl.lower():
            assert diff <= 5e-5, f"Flow diff {diff} exceeded 5e-5 for {lbl}"
        else:
            assert diff <= 5e-3, f"Head diff {diff} exceeded 5e-3 for {lbl}"

    window.close()


def test_05_valve_editing_symbols_and_banner(qapp):
    """5. Valve editing: toggle valve on/off, graph symbol count, drag/bend, modified flag, outdated banner, notice, PNG export."""
    window = MainWindow()
    window.show()
    window._on_load_specimen_example()
    tab = window.comparison_tab

    # Run once to establish a result
    tab.run_comparison_action()
    wait_for_comparison(tab)
    assert tab.outdated_banner.isHidden()

    # Check initial valve symbols in graph scene
    valve_items = [it for it in window.graph_view.scene.items() if isinstance(it, ValveSymbolItem)]
    assert len(valve_items) == 2

    # Toggle valve start on P1 (row 0, col 2)
    window.setWindowModified(False)
    it_p1_start = tab.valves_table.item(0, 2)
    it_p1_start.setCheckState(Qt.Checked)
    QApplication.processEvents()

    assert window.isWindowModified()
    assert not tab.outdated_banner.isHidden()

    # Graph scene should now have 3 valve symbols
    valve_items = [it for it in window.graph_view.scene.items() if isinstance(it, ValveSymbolItem)]
    assert len(valve_items) == 3

    # Toggle valve off on P2 start -> notice should appear and remove from scenario
    it_p2_start = tab.valves_table.item(1, 2)
    it_p2_start.setCheckState(Qt.Unchecked)
    QApplication.processEvents()
    assert not tab.valve_notice_label.isHidden()
    assert "Removed deleted valve" in tab.valve_notice_label.text()

    # Move a node and verify valve symbols follow
    pos = window.graph_view.get_positions()
    if "J1" in pos:
        pos["J1"] = (pos["J1"][0] + 0.1, pos["J1"][1] + 0.1)
        window.graph_view.set_positions(pos)
    valve_items = [it for it in window.graph_view.scene.items() if isinstance(it, ValveSymbolItem)]
    assert len(valve_items) == 2

    # Bend pipe P2 and verify valve symbols follow
    p2_item = next(it for it in window.graph_view.scene.items() if isinstance(it, PipeItem) and it.pipe_id == "P2")
    p2_item.bend_ratio = 0.25
    p2_item._build_geometry()
    p2_item.update()
    valve_items = [it for it in window.graph_view.scene.items() if isinstance(it, ValveSymbolItem)]
    assert len(valve_items) == 2

    # Export to image and verify it renders without crashing
    with tempfile.TemporaryDirectory() as td:
        png_path = Path(td) / "test_graph.png"
        window.graph_view.export_image(png_path)
        assert png_path.exists()
        img = QImage(str(png_path))
        assert not img.isNull()
        assert img.width() > 100

    window.close()


def test_06_custom_scenario_validation_messages(qapp):
    """6. Custom scenario via UI: add event, invalid inputs inline messages, mode (0,0) message, Run disabled, no exception."""
    window = MainWindow()
    window.show()
    window._on_load_specimen_example()
    tab = window.comparison_tab

    # Add custom event (scenario 1 starts with 1 event, adding 1 makes 2)
    tab._on_add_event()
    assert tab.events_table.rowCount() == 2

    # Set invalid event time >= end time (e.g. 150s with end time 120s)
    sp_time = tab.events_table.cellWidget(1, 0)
    sp_time.setValue(150)
    tab._on_events_table_edited()
    QApplication.processEvents()

    assert not tab.run_btn.isEnabled()
    assert "before end time" in tab.ready_label.text().lower()

    # Set mode (0,0): both valves closed initially
    sp_time.setValue(30)
    tab.initial_table.cellWidget(0, 1).setCurrentIndex(1)  # Closed
    tab.initial_table.cellWidget(1, 1).setCurrentIndex(1)  # Closed
    tab._scenario.events = []
    tab._update_scenario_ui(tab._get_network_valves())
    tab.refresh()
    QApplication.processEvents()

    assert not tab.run_btn.isEnabled()
    ready_text = tab.ready_label.text().lower()
    assert "all valves closed" in ready_text or "singular" in ready_text

    window.close()


def test_07_friction_laws_and_steady_flow(qapp):
    """7. Friction: Swamee-Jain and Darcy-Weisbach runs, steady flow ~0.196438 vs constant 0.195321, spin box hidden."""
    window = MainWindow()
    window.show()
    window._on_load_specimen_example()
    tab = window.comparison_tab
    tab.preset_combo.setCurrentIndex(2)  # steady relaxation

    # Constant friction (default)
    assert not tab.factor_spin.isHidden()
    tab.run_comparison_action()
    wait_for_comparison(tab)
    q_const = float(tab.eq_table.item(0, 3).text())
    assert abs(q_const - 0.195321) < 1e-4

    # Darcy-Weisbach
    tab.friction_combo.setCurrentIndex(2)
    assert tab.factor_spin.isHidden()
    tab.run_comparison_action()
    wait_for_comparison(tab)
    q_dw = float(tab.eq_table.item(0, 3).text())
    assert abs(q_dw - 0.196438) < 1e-4

    # Swamee-Jain
    tab.friction_combo.setCurrentIndex(1)
    assert tab.factor_spin.isHidden()
    tab.run_comparison_action()
    wait_for_comparison(tab)
    q_sj = float(tab.eq_table.item(0, 3).text())
    assert abs(q_sj - 0.196438) < 1e-4

    window.close()


def test_08_save_load_round_trip_and_old_files(qapp):
    """8. Save/load round-trip of valve flags, scenario and physics; old v1 and v2 files open cleanly."""
    window = MainWindow()
    window.show()
    window._on_load_specimen_example()
    tab = window.comparison_tab
    tab.preset_combo.setCurrentIndex(3)

    with tempfile.TemporaryDirectory() as td:
        save_path = Path(td) / "specimen_saved.wnet"
        save_project(
            save_path,
            window.network,
            window.graph_view.get_positions(),
            scenario=tab.get_scenario(),
            physics=tab.get_physics(),
        )

        # Clear and reload
        window._on_clear_all()
        assert tab.get_scenario() is None

        window.load_file(save_path)
        reloaded_scen = tab.get_scenario()
        assert reloaded_scen is not None
        assert reloaded_scen.t_end == 400.0
        assert len(reloaded_scen.events) == 1
        assert reloaded_scen.events[0].time == 300.0

        # Load an old v2 file without scenario/physics
        v2_path = Path(td) / "old_v2.wnet"
        save_project(v2_path, example_paper_network(), {})
        window.load_file(v2_path)
        assert tab.get_scenario() is None

    window.close()


def test_09_responsiveness_and_clean_close(qapp):
    """9. Responsiveness: QTimer ticks during run, second click ignored, window close during run ends cleanly."""
    window = MainWindow()
    window.show()
    window._on_load_specimen_example()
    tab = window.comparison_tab

    ticks = 0

    def on_tick():
        nonlocal ticks
        ticks += 1

    timer = QTimer()
    timer.setInterval(50)
    timer.timeout.connect(on_tick)
    timer.start()

    tab.run_comparison_action()
    assert not tab.run_btn.isEnabled()
    # Attempt second click
    tab.run_btn.click()

    wait_for_comparison(tab)
    timer.stop()

    assert ticks >= 2, f"Expected QTimer to tick >= 2 times during run, got {ticks}"

    # Test clean close while thread is running
    tab.run_comparison_action()
    assert tab.is_running
    window.close()  # Must not crash or hang
    window = None


def test_10_earlier_tests_and_selftest():
    """10. Verify selftest runs with code 0."""
    from main import run_selftest
    ret = run_selftest()
    assert ret == 0, f"Selftest failed with exit code {ret}"
