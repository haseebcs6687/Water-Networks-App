"""tests/test_release_v2.py – Release verification test suite for v2.0.0.

Covers:
  (i) Physics widgets round-trip and Swamee-Jain scenario 1 steady Q.
  (ii) Version string 2.0.0 parity across app_info, version_info, README, CHANGELOG, and window title.
  (iii) Help dialogs build and show without exec().
  (iv) Acceptance report generation and value verification.
  (v) specimen_matlab.wnet load/run and EPANET .inp files validation.
  (vi) Quoted UI names in README.txt exist in ui/*.py.
"""

import math
import os
import re
import glob
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication, QLabel, QTextEdit, QMessageBox, QFileDialog

from app_info import __version__, APP_NAME
from core.models import Network
from core.examples import specimen_network, specimen_scenario, specimen_physics
from core.comparison import run_comparison
from core.io import load_project_full
from core.epanet_runner import run_epanet_inp
from ui.comparison_tab import ComparisonTab
from ui.main_window import MainWindow
import tools.make_acceptance_report as mar

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    # Monkeypatch modal dialogs so tests never hang
    QMessageBox.information = lambda *args, **kwargs: QMessageBox.Ok
    QMessageBox.warning = lambda *args, **kwargs: QMessageBox.Ok
    QMessageBox.critical = lambda *args, **kwargs: QMessageBox.Ok
    QMessageBox.question = lambda *args, **kwargs: QMessageBox.Discard
    QFileDialog.getOpenFileName = lambda *args, **kwargs: ("", "")
    QFileDialog.getSaveFileName = lambda *args, **kwargs: ("", "")
    return app


def test_physics_widgets_round_trip(qapp):
    """(i) Physics widgets round trip: nu text '1.0219e-06', g 9.81456, f 0.02, rel error < 1e-15,

    and Swamee-Jain scenario 1 through UI gives steady Q = 0.196438 +- 1e-6.
    """
    net, _ = specimen_network()
    tab = ComparisonTab(net)

    phys = specimen_physics()
    phys.nu = 1.0219e-06
    phys.g = 9.81456
    phys.friction_factor = 0.02
    phys.friction_mode = "constant"

    tab.set_physics(phys)

    # 1. Widget values and formatted text
    assert "1.0219e-06" in tab.nu_spin.text(), f"Expected '1.0219e-06' in nu_spin text, got {tab.nu_spin.text()!r}"
    assert abs(tab.g_spin.value() - 9.81456) < 1e-12
    assert abs(tab.factor_spin.value() - 0.02) < 1e-12

    # 2. Round-trip read back
    read_phys = tab.get_physics()
    assert abs(read_phys.nu - phys.nu) / phys.nu < 1e-15
    assert abs(read_phys.g - phys.g) / phys.g < 1e-15
    assert abs(read_phys.friction_factor - phys.friction_factor) / phys.friction_factor < 1e-15

    # 3. Swamee-Jain scenario 1 steady Q
    tab.friction_combo.setCurrentIndex(1)
    tab._on_friction_mode_changed(1)
    phys_sj = tab.get_physics()
    assert phys_sj.friction_mode == "swamee_jain"

    tab.preset_combo.setCurrentIndex(1)
    tab._on_preset_changed(1)
    sc1 = tab.get_scenario()

    res_sj = run_comparison(net, sc1, phys_sj)
    flow_eqs = [eq for eq in res_sj.equilibrium if "Pipe_1_Flow" in eq["label"]]
    assert len(flow_eqs) > 0
    q_steady = flow_eqs[0]["dae_eq"]
    assert abs(q_steady - 0.196438) <= 1e-6, f"Expected steady Q = 0.196438 +- 1e-6, got {q_steady}"

    tab.deleteLater()


def test_version_string_identical(qapp):
    """(ii) Version string 2.0.0 identical in app_info.py, version_info.txt, README.md, CHANGELOG.md, and window title."""
    expected_version = "2.0.0"

    # 1. app_info.py
    assert __version__ == expected_version

    # 2. version_info.txt
    version_info_path = REPO_ROOT / "version_info.txt"
    assert version_info_path.exists()
    vinfo_text = version_info_path.read_text(encoding="utf-8")
    assert f"2, 0, 0, 0" in vinfo_text or f"2.0.0" in vinfo_text

    # 3. README.md
    readme_path = REPO_ROOT / "README.md"
    assert readme_path.exists()
    readme_text = readme_path.read_text(encoding="utf-8")
    assert expected_version in readme_text

    # 4. CHANGELOG.md
    changelog_path = REPO_ROOT / "CHANGELOG.md"
    assert changelog_path.exists()
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert f"[{expected_version}]" in changelog_text or f"v{expected_version}" in changelog_text or f"Version {expected_version}" in changelog_text

    # 5. Window title
    win = MainWindow()
    try:
        title = win.windowTitle()
        assert expected_version in title, f"Expected {expected_version} in window title, got {title}"
    finally:
        win.setWindowModified(False)
        win.close()
        win.deleteLater()


def test_help_dialogs_build_and_show(qapp):
    """(iii) The three Help dialogs build and show without exec()."""
    win = MainWindow()
    try:
        # 1. About dialog
        about_dlg = win._create_about_dialog()
        about_dlg.show()
        assert about_dlg.windowTitle() == "About Water Network Modeler"
        about_labels = [w.text() for w in about_dlg.findChildren(QLabel)]
        about_full_text = " ".join(about_labels)
        assert "Water Network Modeler 2.0.0" in about_full_text
        about_dlg.close()
        about_dlg.deleteLater()

        # 2. Third-party notices dialog
        notices_dlg = win._create_third_party_notices_dialog()
        notices_dlg.show()
        assert notices_dlg.windowTitle() == "Third-party notices"
        text_edits = notices_dlg.findChildren(QTextEdit)
        assert len(text_edits) == 1
        notices_content = text_edits[0].toPlainText()
        assert "EPANET" in notices_content
        assert "Open Water Analytics" in notices_content
        notices_dlg.close()
        notices_dlg.deleteLater()

        # 3. How to compare dialog
        how_dlg = win._create_how_to_compare_dialog()
        how_dlg.show()
        assert how_dlg.windowTitle() == "How to compare with EPANET"
        how_labels = [w.text() for w in how_dlg.findChildren(QLabel)]
        how_full_text = " ".join(how_labels)
        assert "Build the network" in how_full_text
        assert "Comparison with EPANET" in how_full_text
        how_dlg.close()
        how_dlg.deleteLater()
    finally:
        win.setWindowModified(False)
        win.close()
        win.deleteLater()


def test_acceptance_report_generation():
    """(iv) tools/make_acceptance_report.py runs and 2-3 numbers parsed from the written file equal a fresh computation."""
    mar.generate_acceptance_report()

    report_path = REPO_ROOT / "release" / "ACCEPTANCE_REPORT.md"
    assert report_path.exists()
    text = report_path.read_text(encoding="utf-8")

    # Fresh computation
    g = 9.81456
    Area = math.pi * 0.40**2 / 4.0
    b1_comp = g * Area / 400.0
    b2_comp = g * Area / 250.0

    # Parse and check b1 and b2
    assert f"{b1_comp:.6e}" in text
    assert f"{b2_comp:.6e}" in text

    # Parse and check Dirac value
    assert "+62.16" in text or "+62.1557" in text

    # Check that .txt copy exists and has matching length
    txt_path = REPO_ROOT / "release" / "ACCEPTANCE_REPORT.txt"
    assert txt_path.exists()
    assert len(txt_path.read_text(encoding="utf-8")) == len(text)


def test_specimen_matlab_and_epanet_inp():
    """(v) release/examples/specimen_matlab.wnet loads via load_project_full, runs, impulses +62.16/-38.85/+62.16;

    every scenarioN.inp is read by the real engine without warnings.
    """
    wnet_path = REPO_ROOT / "release" / "examples" / "specimen_matlab.wnet"
    proj = load_project_full(wnet_path)
    net = proj.network
    pos = proj.positions
    scenario = proj.scenario
    physics = proj.physics
    assert scenario is not None
    assert physics is not None

    res = run_comparison(net, scenario, physics, positions=pos)
    assert len(res.impulses) == 3

    coeffs = [imp["coefficient"] for imp in res.impulses]
    # Check +62.16 / -38.85 / +62.16
    assert any(abs(c - (-38.8516)) < 0.05 for c in coeffs)
    assert sum(1 for c in coeffs if abs(c - 62.1626) < 0.05) == 2

    # Every scenarioN.inp is read by real EPANET engine without errors
    for sc_id in range(1, 6):
        inp_file = REPO_ROOT / "release" / "examples" / f"scenario{sc_id}.inp"
        assert inp_file.exists()
        ep_res = run_epanet_inp(str(inp_file))
        assert len(ep_res.t) > 0
        assert len(ep_res.warnings) == 0


def test_readme_quoted_ui_names():
    """(vi) README.txt: every quoted UI name exists as a string in ui/*.py."""
    readme_path = REPO_ROOT / "release" / "README.txt"
    assert readme_path.exists()
    readme_text = readme_path.read_text(encoding="utf-8")

    quotes = re.findall(r'"([^"\n]+)"', readme_text)

    # Exclude system/file names that are not UI widget labels
    non_ui = {
        "WaterNetworkModeler.exe",
        "Windows protected your PC",
        "More info",
        "Run anyway",
        "examples\\",
        "Create_Desktop_Shortcut.bat",
        "Water Network Modeler",
    }
    ui_quotes = [q for q in quotes if q not in non_ui]

    ui_files = list((REPO_ROOT / "ui").glob("*.py"))
    assert len(ui_files) > 0
    ui_code = " ".join(f.read_text(encoding="utf-8") for f in ui_files)

    for q in ui_quotes:
        assert q in ui_code, f"Quoted UI name {q!r} from README.txt not found in any ui/*.py file"
