"""Left control panel for adding and deleting nodes and pipes."""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QComboBox, QPushButton,
    QCheckBox, QDoubleSpinBox, QTableWidget, QTableWidgetItem,
    QMessageBox, QLabel, QHeaderView
)


class BuildPanel(QWidget):
    node_added = Signal(str)  # node_type
    pipe_added = Signal(str, str, bool, float)  # start_id, end_id, has_pump, pump_power
    node_deleted = Signal(str)  # node_id
    pipe_deleted = Signal(str)  # pipe_id
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self._current_network = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # 1. Add Node Group
        node_group = QGroupBox("Add Node")
        node_layout = QHBoxLayout(node_group)
        self.node_type_combo = QComboBox()
        self.node_type_combo.addItems(["Junction", "Tank", "Reservoir"])
        self.add_node_btn = QPushButton("Add Node")
        self.add_node_btn.clicked.connect(self._on_add_node)
        node_layout.addWidget(self.node_type_combo)
        node_layout.addWidget(self.add_node_btn)
        layout.addWidget(node_group)

        # 2. Add Pipe Group
        pipe_group = QGroupBox("Add Pipe")
        pipe_layout = QVBoxLayout(pipe_group)

        combo_row = QHBoxLayout()
        self.start_combo = QComboBox()
        self.end_combo = QComboBox()
        combo_row.addWidget(QLabel("Start:"))
        combo_row.addWidget(self.start_combo)
        combo_row.addWidget(QLabel("End:"))
        combo_row.addWidget(self.end_combo)
        pipe_layout.addLayout(combo_row)

        pump_row = QHBoxLayout()
        self.pump_checkbox = QCheckBox("Contains Pump")
        # Explicit indicator styling for dark themes / scaling
        self.pump_checkbox.setStyleSheet(
            "QCheckBox { font-weight: bold; } "
            "QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #555; border-radius: 2px; } "
            "QCheckBox::indicator:checked { background-color: #007ACC; border-color: #005999; }"
        )

        self.pump_power_spin = QDoubleSpinBox()
        self.pump_power_spin.setRange(0.0, 10000.0)
        self.pump_power_spin.setValue(10.0)
        self.pump_power_spin.setSuffix(" kW")
        self.pump_power_spin.setEnabled(False)
        self.pump_power_spin.setToolTip("stored only, not used in the matrices yet")
        self.pump_checkbox.toggled.connect(self.pump_power_spin.setEnabled)

        pump_row.addWidget(self.pump_checkbox)
        pump_row.addWidget(self.pump_power_spin)
        pipe_layout.addLayout(pump_row)

        self.add_pipe_btn = QPushButton("Add Pipe")
        self.add_pipe_btn.clicked.connect(self._on_add_pipe)
        pipe_layout.addWidget(self.add_pipe_btn)
        layout.addWidget(pipe_group)

        # 3. Nodes Table
        nodes_group = QGroupBox("Nodes")
        nodes_layout = QVBoxLayout(nodes_group)
        self.nodes_table = QTableWidget(0, 2)
        self.nodes_table.setHorizontalHeaderLabels(["ID", "Type"])
        self.nodes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.nodes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.nodes_table.setSelectionMode(QTableWidget.SingleSelection)
        nodes_layout.addWidget(self.nodes_table)

        self.del_node_btn = QPushButton("Delete Selected Node")
        self.del_node_btn.clicked.connect(self._on_delete_node)
        nodes_layout.addWidget(self.del_node_btn)
        layout.addWidget(nodes_group)

        # 4. Pipes Table
        pipes_group = QGroupBox("Pipes")
        pipes_layout = QVBoxLayout(pipes_group)
        self.pipes_table = QTableWidget(0, 4)
        self.pipes_table.setHorizontalHeaderLabels(["ID", "Start", "End", "Pump?"])
        self.pipes_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pipes_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pipes_table.setSelectionMode(QTableWidget.SingleSelection)
        pipes_layout.addWidget(self.pipes_table)

        self.del_pipe_btn = QPushButton("Delete Selected Pipe")
        self.del_pipe_btn.clicked.connect(self._on_delete_pipe)
        pipes_layout.addWidget(self.del_pipe_btn)
        layout.addWidget(pipes_group)

        # 5. Clear All Button
        self.clear_btn = QPushButton("Clear All")
        self.clear_btn.setStyleSheet("background-color: #d9534f; color: white; font-weight: bold;")
        self.clear_btn.clicked.connect(self._on_clear_all)
        layout.addWidget(self.clear_btn)

    def _on_add_node(self):
        ntype = self.node_type_combo.currentText().lower()
        self.node_added.emit(ntype)

    def _on_add_pipe(self):
        start = self.start_combo.currentText()
        end = self.end_combo.currentText()
        if not start or not end:
            QMessageBox.warning(self, "Invalid Selection", "Please select both a start and end node.")
            return
        if start == end:
            QMessageBox.warning(self, "Invalid Pipe", "Start and End node cannot be the same (self-loops not allowed).")
            return
        has_pump = self.pump_checkbox.isChecked()
        power = self.pump_power_spin.value() if has_pump else 0.0
        self.pipe_added.emit(start, end, has_pump, power)

    def update_network(self, network):
        """Update node/pipe dropdowns and table views from the Network instance."""
        self._current_network = network

        node_ids = [n.id for n in network.nodes]
        self.start_combo.blockSignals(True)
        self.end_combo.blockSignals(True)
        self.start_combo.clear()
        self.end_combo.clear()
        self.start_combo.addItems(node_ids)
        self.end_combo.addItems(node_ids)

        # Requirement 0c: Preselect DIFFERENT nodes in Start and End if available
        if len(node_ids) >= 2:
            self.start_combo.setCurrentIndex(0)
            self.end_combo.setCurrentIndex(1)
        elif len(node_ids) == 1:
            self.start_combo.setCurrentIndex(0)
            self.end_combo.setCurrentIndex(0)

        self.start_combo.blockSignals(False)
        self.end_combo.blockSignals(False)

        # Nodes table
        self.nodes_table.setRowCount(len(network.nodes))
        for r, node in enumerate(network.nodes):
            self.nodes_table.setItem(r, 0, QTableWidgetItem(node.id))
            self.nodes_table.setItem(r, 1, QTableWidgetItem(node.type.capitalize()))

        # Pipes table
        self.pipes_table.setRowCount(len(network.pipes))
        for r, pipe in enumerate(network.pipes):
            pump_str = f"Yes ({pipe.pump_power:.1f} kW)" if pipe.has_pump else "No"
            self.pipes_table.setItem(r, 0, QTableWidgetItem(pipe.id))
            self.pipes_table.setItem(r, 1, QTableWidgetItem(pipe.start))
            self.pipes_table.setItem(r, 2, QTableWidgetItem(pipe.end))
            self.pipes_table.setItem(r, 3, QTableWidgetItem(pump_str))

    def _on_delete_node(self):
        row = self.nodes_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a node to delete.")
            return
        node_id = self.nodes_table.item(row, 0).text()
        attached_pipes = []
        if self._current_network is not None:
            attached_pipes = [p for p in self._current_network.pipes if p.start == node_id or p.end == node_id]
        pipe_count = len(attached_pipes)

        msg = f"Are you sure you want to delete node {node_id}?"
        if pipe_count > 0:
            msg += f"\nThis will also delete {pipe_count} pipe(s) attached to it."

        res = QMessageBox.question(self, "Confirm Delete Node", msg, QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            self.node_deleted.emit(node_id)

    def _on_delete_pipe(self):
        row = self.pipes_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a pipe to delete.")
            return
        pipe_id = self.pipes_table.item(row, 0).text()
        res = QMessageBox.question(self, "Confirm Delete Pipe", f"Are you sure you want to delete pipe {pipe_id}?", QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            self.pipe_deleted.emit(pipe_id)

    def _on_clear_all(self):
        res = QMessageBox.question(self, "Confirm Clear All", "Are you sure you want to clear all nodes and pipes?", QMessageBox.Yes | QMessageBox.No)
        if res == QMessageBox.Yes:
            self.cleared.emit()
