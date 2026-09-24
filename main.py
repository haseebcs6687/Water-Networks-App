"""Entry point for Water Network Modeler desktop application."""

import os
import sys
import ctypes
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from app_info import APP_NAME, APP_ID, COMPANY_NAME, __version__, resource_path
from ui.main_window import MainWindow
from core.examples import example_paper_network, example_broken_network
from core.matrices import build_matrices
from core.io import save_project


def setup_exception_hook():
    """Install global exception hook to catch unhandled errors and display dialog."""
    def excepthook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
        tb_str = "".join(tb_lines)

        try:
            local_appdata = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
            log_dir = Path(local_appdata) / APP_ID
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / "error.log"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat()}] Unhandled Exception:\n")
                f.write(tb_str)
                f.write("=" * 60 + "\n")
            log_path_str = str(log_file)
        except Exception as e:
            log_path_str = f"<Unable to write log file: {e}>"

        sys.stderr.write(tb_str)

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Something went wrong")
        msg_box.setText("Something went wrong in Water Network Modeler.")
        msg_box.setInformativeText(
            f"An unexpected error occurred.\n\n"
            f"A detailed error log has been saved to:\n{log_path_str}\n\n"
            f"{exc_type.__name__}: {exc_value}"
        )
        msg_box.setDetailedText(tb_str)
        msg_box.exec()

    sys.excepthook = excepthook


def run_selftest(log_path: Optional[Path] = None) -> int:
    """Run offscreen selftest suite: load examples, verify matrices/checks, render tabs, test I/O."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"

    if log_path is None:
        temp_dir = Path(os.environ.get("TEMP", os.environ.get("TMP", str(Path.home()))))
        log_path = temp_dir / "wnm_selftest.log"

    def write_log(msg: str):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}] {msg}"
        print(line)
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    # Clear log file initially
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"=== WaterNetworkModeler Selftest Log Started ===\n")
    except Exception as e:
        print(f"Failed to initialize log file {log_path}: {e}")

    try:
        write_log("Starting selftest...")
        write_log(f"Platform: {sys.platform}, Python: {sys.version.split()[0]}")
        write_log(f"QT_QPA_PLATFORM: {os.environ.get('QT_QPA_PLATFORM')}")

        # Ensure QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication(["--selftest"])
        app.setStyle("Fusion")
        app.setOrganizationName(COMPANY_NAME)
        app.setApplicationName(APP_ID)

        write_log("Instantiating MainWindow...")
        window = MainWindow()
        window.show()
        app.processEvents()
        write_log("MainWindow initialized and shown offscreen.")

        # 1. Load paper example
        write_log("Loading paper example network...")
        window.network = example_paper_network()
        window.refresh()
        app.processEvents()

        num_nodes = len(window.network.nodes)
        num_pipes = len(window.network.pipes)
        write_log(f"Paper network loaded: {num_nodes} nodes, {num_pipes} pipes.")
        assert num_nodes == 6, f"Expected 6 nodes in paper network, got {num_nodes}"
        assert num_pipes == 8, f"Expected 8 pipes in paper network, got {num_pipes}"

        # 2. Build matrices & checks for paper example
        write_log("Verifying matrices and checks on paper network...")
        mat = build_matrices(window.network.to_dict())
        assert mat is not None, "Matrices could not be built for paper network"
        assert mat["K_dimension"] == 28, f"Expected K=28, got {mat['K_dimension']}"
        banner_text = window.checks_view.banner.text()
        assert "Regular" in banner_text, f"Expected 'Regular' banner, got {banner_text}"
        write_log(f"Paper network verified: Regular banner confirmed, K={mat['K_dimension']}.")

        # 3. Render graph and every tab once for paper example
        write_log("Rendering graph and all right-panel tabs for paper network...")
        window.graph_view.draw_network(window.network)
        tab_count = window.right_tabs.count()
        for idx in range(tab_count):
            window.right_tabs.setCurrentIndex(idx)
            app.processEvents()
            tab_name = window.right_tabs.tabText(idx)
            write_log(f"  Rendered tab [{idx}]: {tab_name}")
        app.processEvents()

        # 4. Load broken example
        write_log("Loading broken example network...")
        window.network = example_broken_network()
        window.refresh()
        app.processEvents()

        broken_nodes = len(window.network.nodes)
        broken_pipes = len(window.network.pipes)
        write_log(f"Broken network loaded: {broken_nodes} nodes, {broken_pipes} pipes.")

        # 5. Build matrices & checks for broken example
        write_log("Verifying matrices and checks on broken network...")
        mat_broken = build_matrices(window.network.to_dict())
        assert mat_broken is not None, "Matrices could not be built for broken network"
        broken_banner = window.checks_view.banner.text()
        assert "NOT regular" in broken_banner, f"Expected 'NOT regular' banner, got {broken_banner}"
        warnings_count = window.checks_view.warnings_table.rowCount()
        assert warnings_count >= 2, f"Expected >= 2 warnings for broken network, got {warnings_count}"
        write_log(f"Broken network verified: 'NOT regular' banner and {warnings_count} warnings confirmed.")

        # 6. Render graph and every tab once for broken example
        write_log("Rendering graph and all right-panel tabs for broken network...")
        window.graph_view.draw_network(window.network)
        for idx in range(tab_count):
            window.right_tabs.setCurrentIndex(idx)
            app.processEvents()
            tab_name = window.right_tabs.tabText(idx)
            write_log(f"  Rendered tab [{idx}]: {tab_name}")
        app.processEvents()

        # 7. Save and reload a temporary .wnet
        write_log("Testing project save and reload to temporary .wnet...")
        window.network = example_paper_network()
        window.refresh()
        temp_dir = Path(os.environ.get("TEMP", os.environ.get("TMP", str(Path.home()))))
        temp_wnet = temp_dir / f"wnm_selftest_temp_{os.getpid()}.wnet"

        save_project(temp_wnet, window.network, window.graph_view.get_positions())
        assert temp_wnet.is_file(), f"Saved project file does not exist: {temp_wnet}"
        file_size = temp_wnet.stat().st_size
        write_log(f"Project saved to {temp_wnet} ({file_size} bytes).")

        # Clear and verify empty
        window.network.clear()
        window.refresh()
        app.processEvents()
        assert len(window.network.nodes) == 0, "Network should be empty after clear"
        write_log("Network cleared.")

        # Reload from temp file
        window.load_file(temp_wnet)
        app.processEvents()
        reloaded_nodes = len(window.network.nodes)
        reloaded_pipes = len(window.network.pipes)
        assert reloaded_nodes == 6, f"Expected 6 reloaded nodes, got {reloaded_nodes}"
        assert reloaded_pipes == 8, f"Expected 8 reloaded pipes, got {reloaded_pipes}"
        assert "Regular" in window.checks_view.banner.text(), "Reloaded network should be regular"
        write_log("Project successfully reloaded and verified.")

        # Cleanup temp file
        try:
            temp_wnet.unlink()
            write_log("Temporary .wnet file deleted.")
        except Exception as e:
            write_log(f"Warning: could not delete temp file: {e}")

        window.close()
        app.processEvents()

        write_log("=== Selftest PASSED (code 0) ===")
        return 0

    except Exception as e:
        tb = traceback.format_exc()
        write_log(f"FAIL: Selftest exception: {e}\n{tb}")
        write_log("=== Selftest FAILED (code 1) ===")
        return 1


def main():
    setup_exception_hook()

    if "--selftest" in sys.argv:
        ret = run_selftest()
        sys.exit(ret)

    # Windows taskbar icon setup
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except Exception as e:
            print(f"Warning: SetCurrentProcessExplicitAppUserModelID failed: {e}")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setOrganizationName(COMPANY_NAME)
    app.setApplicationName(APP_ID)

    # Set application and window icon
    icon_path = resource_path("assets/app.ico")
    if icon_path.exists():
        app_icon = QIcon(str(icon_path))
        app.setWindowIcon(app_icon)
    else:
        app_icon = None

    window = MainWindow()
    if app_icon:
        window.setWindowIcon(app_icon)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
