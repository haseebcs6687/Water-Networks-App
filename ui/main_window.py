"""Main application window wiring build panel, views, menus, and file I/O."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QTabWidget, QSplitter,
    QMessageBox, QStatusBar, QFileDialog, QScrollArea, QApplication
)

from core.models import Network
from core.matrices import build_matrices
from core.io import save_project, load_project
from core.examples import example_paper_network, example_broken_network

from ui.build_panel import BuildPanel
from ui.graph_view import GraphView
from ui.matrix_view import MatrixView
from ui.checks_view import ChecksView
from ui.incidence_view import IncidenceView


from app_info import APP_NAME, __version__

class MainWindow(QMainWindow):
    """Main desktop application window for Water Network Modeler."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.network = Network()
        self._current_filepath: Optional[Path] = None
        self._last_dir: Path = Path.home()

        self.setMinimumSize(1000, 600)
        self._init_ui()
        self._size_and_center_window()
        self.refresh()
        self.setWindowModified(False)

    def _size_and_center_window(self):
        screen = self.screen() or QApplication.primaryScreen()
        if screen:
            geom = screen.availableGeometry()
            w, h = int(geom.width() * 0.9), int(geom.height() * 0.9)
            self.resize(w, h)
            self.move(geom.x() + (geom.width() - w) // 2, geom.y() + (geom.height() - h) // 2)

    def _update_window_title(self):
        filename = self._current_filepath.name if self._current_filepath else "Untitled"
        self.setWindowTitle(f"Water Network Modeler - {filename}[*]")

    def _init_ui(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        self._add_action(file_menu, "&New", QKeySequence.New, self._on_new)
        self._add_action(file_menu, "&Open...", QKeySequence.Open, self._on_open)
        self._add_action(file_menu, "&Save", QKeySequence.Save, self._on_save)
        self._add_action(file_menu, "Save &As...", QKeySequence.SaveAs, self._on_save_as)
        file_menu.addSeparator()

        ex_menu = file_menu.addMenu("Load &Example")
        ex_menu.addAction("Paper sample network").triggered.connect(lambda: self._on_load_example(example_paper_network))
        ex_menu.addAction("Broken network (demo of warnings)").triggered.connect(lambda: self._on_load_example(example_broken_network))
        file_menu.addSeparator()

        file_menu.addAction("E&xit").triggered.connect(self.close)

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About").triggered.connect(self._show_about)

        self.setStatusBar(QStatusBar(self))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        splitter = QSplitter(Qt.Horizontal)

        self.build_panel = BuildPanel()
        self.build_panel.node_added.connect(self._on_add_node)
        self.build_panel.pipe_added.connect(self._on_add_pipe)
        self.build_panel.node_deleted.connect(self._on_delete_node)
        self.build_panel.pipe_deleted.connect(self._on_delete_pipe)
        self.build_panel.node_updated.connect(self._on_update_node)
        self.build_panel.pipe_updated.connect(self._on_update_pipe)
        self.build_panel.cleared.connect(self._on_clear_all)

        scroll_area = QScrollArea()
        scroll_area.setWidget(self.build_panel)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFixedWidth(330)
        splitter.addWidget(scroll_area)

        self.right_tabs = QTabWidget()
        self.graph_view = GraphView()
        self.matrix_view = MatrixView()
        self.checks_view = ChecksView()
        self.incidence_view = IncidenceView()

        self._syncing_selection = False

        self.checks_view.warning_double_clicked.connect(self._on_warning_double_clicked)
        self.graph_view.positions_changed.connect(self._on_positions_changed)
        self.graph_view.node_clicked.connect(self._on_graph_node_clicked)
        self.graph_view.pipe_clicked.connect(self._on_graph_pipe_clicked)
        self.graph_view.background_clicked.connect(self._on_graph_background_clicked)
        self.graph_view.relayout_btn.clicked.connect(self._mark_edited)

        self.build_panel.node_selected.connect(self._on_panel_node_selected)
        self.build_panel.pipe_selected.connect(self._on_panel_pipe_selected)
        self.build_panel.selection_cleared.connect(self._on_panel_selection_cleared)

        self.right_tabs.addTab(self.graph_view, "Network")
        self.right_tabs.addTab(self.matrix_view, "Matrices")
        self.right_tabs.addTab(self.checks_view, "Checks")
        self.right_tabs.addTab(self.incidence_view, "Incidence")

        splitter.addWidget(self.right_tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)
        self._update_window_title()

    def _add_action(self, menu, text, shortcut, slot):
        act = QAction(text, self)
        act.setShortcut(shortcut)
        act.triggered.connect(slot)
        menu.addAction(act)

    def _show_about(self):
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<b>{APP_NAME}</b><br>Version {__version__}<br><br>"
            "Based on the research paper on water network solvability."
        )

    def _maybe_save_changes(self) -> bool:
        if not self.isWindowModified():
            return True
        filename = self._current_filepath.name if self._current_filepath else "Untitled"
        res = QMessageBox.question(
            self, "Unsaved Changes", f"Do you want to save changes to {filename}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
        )
        if res == QMessageBox.Save:
            return self._on_save()
        elif res == QMessageBox.Discard:
            return True
        return False

    def closeEvent(self, event):
        if self._maybe_save_changes():
            event.accept()
        else:
            event.ignore()

    def load_file(self, path: Path) -> None:
        path = Path(path)
        loaded_net, pos = load_project(path)
        self.network = loaded_net
        self.graph_view.set_positions(pos)
        self._current_filepath = path
        self._last_dir = path.parent
        self.refresh()
        self.setWindowModified(False)
        self._update_window_title()

    def _on_new(self):
        if not self._maybe_save_changes():
            return
        self.network.clear()
        self.graph_view.set_positions({})
        self._current_filepath = None
        self.refresh()
        self.setWindowModified(False)
        self._update_window_title()

    def _on_open(self):
        if not self._maybe_save_changes():
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Project File", str(self._last_dir), "Water Network Files (*.wnet)"
        )
        if path_str:
            try:
                self.load_file(Path(path_str))
            except Exception as e:
                self._handle_error("Failed to load project", e)

    def _on_save(self) -> bool:
        if self._current_filepath is None:
            return self._on_save_as()
        try:
            save_project(self._current_filepath, self.network, self.graph_view.get_positions())
            self.setWindowModified(False)
            self._update_window_title()
            return True
        except Exception as e:
            self._handle_error("Failed to save project", e)
            return False

    def _on_save_as(self) -> bool:
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", str(self._last_dir / "network.wnet"), "Water Network Files (*.wnet)"
        )
        if not path_str:
            return False
        path = Path(path_str)
        self._last_dir = path.parent
        self._current_filepath = path
        return self._on_save()

    def _on_load_example(self, example_factory):
        if not self._maybe_save_changes():
            return
        self.network = example_factory()
        self.graph_view.set_positions({})
        self._current_filepath = None
        self.refresh()
        self.setWindowModified(False)
        self._update_window_title()

    def _on_add_node(self, ntype: str, params: Optional[dict] = None):
        try:
            kwargs = dict(params) if params else {}
            self.network.add_node(ntype, **kwargs)
            self._mark_edited()
        except Exception as e:
            self._handle_error("Failed to add node", e)

    def _on_add_pipe(self, start: str, end: str, has_pump: bool, power: float, params: Optional[dict] = None):
        try:
            kwargs = dict(params) if params else {}
            self.network.add_pipe(start, end, has_pump=has_pump, pump_power=power, **kwargs)
            self._mark_edited()
        except Exception as e:
            self._handle_error("Failed to add pipe", e)

    def _on_update_node(self, node_id: str, fields: dict):
        try:
            self.network.update_node(node_id, **fields)
            self._mark_edited()
        except Exception as e:
            self._handle_error("Failed to update node", e)

    def _on_update_pipe(self, pipe_id: str, fields: dict):
        try:
            self.network.update_pipe(pipe_id, **fields)
            self._mark_edited()
        except Exception as e:
            self._handle_error("Failed to update pipe", e)

    def _on_delete_node(self, node_id: str):
        try:
            self.network.remove_node(node_id)
            self._mark_edited()
        except Exception as e:
            self._handle_error("Failed to delete node", e)

    def _on_delete_pipe(self, pipe_id: str):
        try:
            self.network.remove_pipe(pipe_id)
            self._mark_edited()
        except Exception as e:
            self._handle_error("Failed to delete pipe", e)

    def _on_clear_all(self):
        try:
            self.network.clear()
            self.graph_view.set_positions({})
            self._mark_edited()
        except Exception as e:
            self._handle_error("Failed to clear network", e)

    def _on_positions_changed(self):
        self.setWindowModified(True)
        self._update_window_title()

    def _on_graph_node_clicked(self, node_id: str):
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.build_panel.select_node(node_id)
            self.graph_view.set_selection(node_id=node_id)
        finally:
            self._syncing_selection = False

    def _on_graph_pipe_clicked(self, pipe_id: str):
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.build_panel.select_pipe(pipe_id)
            self.graph_view.set_selection(pipe_id=pipe_id)
        finally:
            self._syncing_selection = False

    def _on_graph_background_clicked(self):
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.build_panel.clear_selection()
            self.graph_view.clear_selection()
        finally:
            self._syncing_selection = False

    def _on_panel_node_selected(self, node_id: str):
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.graph_view.set_selection(node_id=node_id)
        finally:
            self._syncing_selection = False

    def _on_panel_pipe_selected(self, pipe_id: str):
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.graph_view.set_selection(pipe_id=pipe_id)
        finally:
            self._syncing_selection = False

    def _on_panel_selection_cleared(self):
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.graph_view.clear_selection()
        finally:
            self._syncing_selection = False

    def _mark_edited(self):
        self.graph_view.clear_highlight()
        self.setWindowModified(True)
        self.refresh()

    def _on_warning_double_clicked(self, ids: list):
        self.right_tabs.setCurrentWidget(self.graph_view)
        self.graph_view.highlight(ids)

    def _handle_error(self, title: str, exc: Exception):
        msg = str(exc)
        self.statusBar().showMessage(f"Error: {msg}")
        QMessageBox.critical(self, title, f"{title}: {msg}")

    def refresh(self):
        try:
            self.build_panel.update_network(self.network)
            self.graph_view.draw_network(self.network)

            matrices_res = build_matrices(self.network.to_dict()) if self.network.pipes else None
            self.matrix_view.update_matrices(self.network, matrices_res)
            self.checks_view.update_checks(self.network)
            self.incidence_view.update_incidence(self.network)

            num_nodes, num_pipes = len(self.network.nodes), len(self.network.pipes)
            K = matrices_res["K_dimension"] if matrices_res else 0
            self.statusBar().showMessage(f"Nodes: {num_nodes}   Pipes: {num_pipes}   K = {K}")
        except Exception as e:
            msg = str(e)
            self.statusBar().showMessage(f"Error during refresh: {msg}")
            QMessageBox.critical(self, "Refresh Error", f"An error occurred while refreshing the UI:\n{msg}")
