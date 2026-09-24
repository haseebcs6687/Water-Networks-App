"""Widget for rendering directed water networks using matplotlib and NetworkX."""

from collections import defaultdict
from typing import Dict, Tuple, List, Set, Optional

import networkx as nx
import matplotlib
matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton


class GraphView(QWidget):
    """Widget displaying the directed network graph with zoom/pan, re-layout, and element highlighting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos: Dict[str, Tuple[float, float]] = {}
        self._highlight_ids: Set[str] = set()
        self._current_network = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.figure = Figure(figsize=(6, 5), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.ax = self.figure.add_subplot(111)

        top_bar = QHBoxLayout()
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        top_bar.addWidget(self.toolbar)

        self.relayout_btn = QPushButton("Re-layout")
        self.relayout_btn.setToolTip("Recalculate layout for all nodes")
        self.relayout_btn.clicked.connect(self._on_relayout)
        top_bar.addWidget(self.relayout_btn)

        layout.addLayout(top_bar)
        layout.addWidget(self.canvas)

        self._clear_axes()

    def _clear_axes(self):
        self.ax.clear()
        self.ax.set_title("Network Graph")
        self.ax.text(0.5, 0.5, "Add nodes and pipes to view network graph",
                     horizontalalignment='center', verticalalignment='center',
                     transform=self.ax.transAxes, fontsize=12, color='gray')
        self.ax.axis('off')
        self.canvas.draw()

    def _on_relayout(self):
        self._pos.clear()
        if self._current_network:
            self.draw_network(self._current_network)

    def get_positions(self) -> Dict[str, Tuple[float, float]]:
        """Return current canvas node positions."""
        return dict(self._pos)

    def set_positions(self, pos: Dict[str, Tuple[float, float]]) -> None:
        """Set canvas node positions and refresh drawing."""
        self._pos = dict(pos) if pos else {}
        if self._current_network:
            self.draw_network(self._current_network)

    def highlight(self, ids: List[str]) -> None:
        """Highlight specified node/pipe IDs with a red outline."""
        self._highlight_ids = set(ids)
        if self._current_network:
            self.draw_network(self._current_network)

    def clear_highlight(self) -> None:
        """Clear all active graph highlights."""
        if self._highlight_ids:
            self._highlight_ids.clear()
            if self._current_network:
                self.draw_network(self._current_network)

    def draw_network(self, network):
        """Draw the given Network instance on the canvas."""
        self._current_network = network
        self.ax.clear()

        # Requirement 0a: Draw nodes as long as at least 1 node exists (even 0 pipes)
        if not network.nodes:
            self._clear_axes()
            return

        G = nx.MultiDiGraph()
        node_colors = {}
        color_map = {"junction": "#87CEEB", "tank": "#FFD700", "reservoir": "#FA8072"}

        for n in network.nodes:
            G.add_node(n.id, type=n.type)
            node_colors[n.id] = color_map.get(n.type, "#CCCCCC")

        for p in network.pipes:
            label = f"{p.id} ({p.pump_power:.0f}kW)" if p.has_pump else p.id
            G.add_edge(p.start, p.end, id=p.id, has_pump=p.has_pump, power=p.pump_power, label=label)

        # Update node layout preserving existing positions
        current_nodes = set(G.nodes())
        for nid in list(self._pos.keys()):
            if nid not in current_nodes:
                del self._pos[nid]

        if not self._pos:
            self._pos = nx.spring_layout(G, seed=42)
        else:
            fixed_nodes = [n for n in G.nodes() if n in self._pos]
            if len(fixed_nodes) < len(G.nodes()):
                import numpy as np
                rng = np.random.default_rng(42)
                pos_init = dict(self._pos)
                for n in G.nodes():
                    if n not in pos_init:
                        pos_init[n] = rng.uniform(-1, 1, size=2)
                new_pos = nx.spring_layout(G, pos=pos_init, fixed=fixed_nodes, seed=42)
                self._pos.update(new_pos)

        pos = self._pos

        # Draw nodes by type, applying red outline if highlighted
        for ntype, color in color_map.items():
            nlist = [n.id for n in network.nodes if n.type == ntype]
            if nlist:
                for nid in nlist:
                    is_hl = nid in self._highlight_ids
                    ec = "red" if is_hl else "black"
                    lw = 3.0 if is_hl else 1.5
                    nx.draw_networkx_nodes(
                        G, pos, nodelist=[nid], node_color=color,
                        node_size=700, ax=self.ax, edgecolors=ec, linewidths=lw
                    )

        nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', ax=self.ax)

        # Draw edges if pipes exist
        if network.pipes:
            pair_counts = defaultdict(int)
            pair_index = defaultdict(int)

            for u, v, k, data in G.edges(keys=True, data=True):
                pair_key = tuple(sorted([u, v]))
                pair_counts[pair_key] += 1

            for u, v, k, data in G.edges(keys=True, data=True):
                pair_key = tuple(sorted([u, v]))
                count = pair_counts[pair_key]
                idx = pair_index[pair_key]
                pair_index[pair_key] += 1

                if count == 1:
                    rad = 0.0
                else:
                    step = 0.2
                    rad = ((idx + 1) // 2) * step * (1 if idx % 2 == 1 else -1)
                    if u > v:
                        rad = -rad

                conn_style = f"arc3,rad={rad}"
                pipe_id = data.get("id")
                is_hl = pipe_id in self._highlight_ids
                is_pump = data.get("has_pump", False)

                edge_style = "dashed" if is_pump else "solid"
                if is_hl:
                    edge_color = "red"
                    width = 3.5
                else:
                    edge_color = "crimson" if is_pump else "#333333"
                    width = 2.0

                nx.draw_networkx_edges(
                    G, pos, edgelist=[(u, v)],
                    connectionstyle=conn_style,
                    arrowstyle='-|>', arrowsize=18,
                    style=edge_style, edge_color=edge_color,
                    width=width, ax=self.ax
                )

                # Requirement 0e: Readable white rounded background box for edge labels
                edge_label = {(u, v): data["label"]}
                nx.draw_networkx_edge_labels(
                    G, pos, edge_labels=edge_label,
                    connectionstyle=conn_style,
                    font_size=8, font_color=edge_color,
                    ax=self.ax, bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.9)
                )

        # Custom Legend
        legend_elements = [
            Line2D([0], [0], marker='o', color='w', label='Junction', markerfacecolor='#87CEEB', markersize=10, markeredgecolor='black'),
            Line2D([0], [0], marker='o', color='w', label='Tank', markerfacecolor='#FFD700', markersize=10, markeredgecolor='black'),
            Line2D([0], [0], marker='o', color='w', label='Reservoir', markerfacecolor='#FA8072', markersize=10, markeredgecolor='black'),
            Line2D([0], [0], color='#333333', linestyle='-', lw=2, label='Pipe'),
            Line2D([0], [0], color='crimson', linestyle='--', lw=2, label='Pump')
        ]
        self.ax.legend(handles=legend_elements, loc='upper right', framealpha=0.9)

        self.ax.axis('off')
        self.figure.tight_layout()
        self.canvas.draw()
