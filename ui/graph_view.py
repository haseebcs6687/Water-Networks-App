"""Widget for rendering directed water networks using Qt QGraphicsScene and QGraphicsView."""

import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple, List, Set, Optional

import networkx as nx

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QColor, QPen, QBrush, QFont, QFontMetrics, QPainter,
    QPainterPath, QPolygonF, QImage
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QGraphicsView,
    QGraphicsScene, QGraphicsItem, QGraphicsSimpleTextItem, QFileDialog
)

# ---------------------------------------------------------------------------
# Coordinate Conversion Constants & Helpers
# ---------------------------------------------------------------------------

SCALE: float = 300.0
NODE_RADIUS: float = 20.0


def model_to_scene(x: float, y: float, scale: float = SCALE) -> Tuple[float, float]:
    """Convert model/layout coordinate (y up) to Qt scene coordinate (y down)."""
    return (float(x) * scale, -float(y) * scale)


def scene_to_model(sx: float, sy: float, scale: float = SCALE) -> Tuple[float, float]:
    """Convert Qt scene coordinate (y down) to model/layout coordinate (y up)."""
    return (float(sx) / scale, -float(sy) / scale)


# ---------------------------------------------------------------------------
# Graphics Items
# ---------------------------------------------------------------------------


class NodeItem(QGraphicsItem):
    """Circular node item with centered ID label."""

    def __init__(self, node_id: str, node_type: str, pos: QPointF, parent=None):
        super().__init__(parent)
        self.node_id = node_id
        self.node_type = node_type.lower()
        self.setPos(pos)
        self.setZValue(10)
        self._highlighted = False

        self.color_map = {
            "junction": QColor("#87CEEB"),
            "tank": QColor("#FFD700"),
            "reservoir": QColor("#FA8072"),
        }
        self.base_color = self.color_map.get(self.node_type, QColor("#CCCCCC"))

    def set_highlighted(self, val: bool):
        if self._highlighted != val:
            self._highlighted = val
            self.update()

    def boundingRect(self) -> QRectF:
        r = NODE_RADIUS + 4
        return QRectF(-r, -r, 2 * r, 2 * r)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        if self._highlighted:
            pen = QPen(QColor("red"), 3.0)
        else:
            pen = QPen(QColor("#000000"), 1.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(self.base_color))
        painter.drawEllipse(QPointF(0, 0), NODE_RADIUS, NODE_RADIUS)

        # Center node ID label
        painter.setPen(QColor("#000000"))
        font = QFont("Segoe UI", 9, QFont.Bold)
        painter.setFont(font)
        painter.drawText(
            QRectF(-NODE_RADIUS, -NODE_RADIUS, 2 * NODE_RADIUS, 2 * NODE_RADIUS),
            Qt.AlignCenter,
            self.node_id
        )


class PipeItem(QGraphicsItem):
    """Directed pipe item stopping at node boundaries with arrow and mid-curve label."""

    def __init__(
        self,
        pipe_id: str,
        start_pos: QPointF,
        end_pos: QPointF,
        has_pump: bool = False,
        label_text: str = "",
        curvature: float = 0.0,
        parent=None,
    ):
        super().__init__(parent)
        self.pipe_id = pipe_id
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.has_pump = has_pump
        self.label_text = label_text or pipe_id
        self.curvature = curvature
        self.setZValue(5)
        self._highlighted = False

        self._build_geometry()

    def _build_geometry(self):
        p1 = self.start_pos
        p2 = self.end_pos
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length < 1e-4:
            ux, uy = 1.0, 0.0
            nx, ny = 0.0, 1.0
        else:
            ux, uy = dx / length, dy / length
            nx, ny = -uy, ux

        # Midpoint and control point for quadratic Bezier
        mx = (p1.x() + p2.x()) / 2.0
        my = (p1.y() + p2.y()) / 2.0

        if abs(self.curvature) < 1e-4:
            qx, qy = mx, my
        else:
            offset = self.curvature * length * 0.5
            qx = mx + nx * offset
            qy = my + ny * offset

        # Start point at start node boundary
        v1x, v1y = qx - p1.x(), qy - p1.y()
        l1 = math.hypot(v1x, v1y)
        if l1 > NODE_RADIUS:
            start_pt = QPointF(p1.x() + (v1x / l1) * NODE_RADIUS, p1.y() + (v1y / l1) * NODE_RADIUS)
        else:
            start_pt = p1

        # End point at end node boundary
        v2x, v2y = p2.x() - qx, p2.y() - qy
        l2 = math.hypot(v2x, v2y)
        if l2 > NODE_RADIUS:
            end_pt = QPointF(p2.x() - (v2x / l2) * NODE_RADIUS, p2.y() - (v2y / l2) * NODE_RADIUS)
        else:
            end_pt = p2

        self.path = QPainterPath()
        self.path.moveTo(start_pt)
        ctrl_pt = QPointF(qx, qy)
        if abs(self.curvature) < 1e-4:
            self.path.lineTo(end_pt)
        else:
            self.path.quadTo(ctrl_pt, end_pt)

        # Arrowhead at end_pt
        tx = end_pt.x() - ctrl_pt.x()
        ty = end_pt.y() - ctrl_pt.y()
        tlen = math.hypot(tx, ty)
        if tlen > 1e-4:
            tux, tuy = tx / tlen, ty / tlen
        else:
            tux, tuy = ux, uy
        tnx, tny = -tuy, tux

        arrow_len = 13.0
        arrow_half_width = 5.0
        tip = end_pt
        left_barb = QPointF(
            tip.x() - tux * arrow_len + tnx * arrow_half_width,
            tip.y() - tuy * arrow_len + tny * arrow_half_width
        )
        right_barb = QPointF(
            tip.x() - tux * arrow_len - tnx * arrow_half_width,
            tip.y() - tuy * arrow_len - tny * arrow_half_width
        )
        self.arrow_poly = QPolygonF([tip, left_barb, right_barb])

        # Curve midpoint for label box
        mid_t = 0.5
        if abs(self.curvature) < 1e-4:
            self.label_pos = QPointF((start_pt.x() + end_pt.x()) / 2.0, (start_pt.y() + end_pt.y()) / 2.0)
        else:
            mid_x = (1 - mid_t)**2 * start_pt.x() + 2 * (1 - mid_t) * mid_t * qx + mid_t**2 * end_pt.x()
            mid_y = (1 - mid_t)**2 * start_pt.y() + 2 * (1 - mid_t) * mid_t * qy + mid_t**2 * end_pt.y()
            self.label_pos = QPointF(mid_x, mid_y)

    def set_highlighted(self, val: bool):
        if self._highlighted != val:
            self._highlighted = val
            self.update()

    def boundingRect(self) -> QRectF:
        rect = self.path.boundingRect()
        rect = rect.united(self.arrow_poly.boundingRect())
        return rect.adjusted(-30, -30, 30, 30)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)

        # 1. Curve
        if self._highlighted:
            line_pen = QPen(QColor("red"), 3.5)
            color = QColor("red")
        else:
            color = QColor("#DC143C") if self.has_pump else QColor("#333333")
            style = Qt.DashLine if self.has_pump else Qt.SolidLine
            line_pen = QPen(color, 2.0, style)

        painter.setPen(line_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path)

        # 2. Arrowhead
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(color))
        painter.drawPolygon(self.arrow_poly)

        # 3. Label with white rounded background
        font = QFont("Segoe UI", 8)
        painter.setFont(font)
        fm = QFontMetrics(font)
        tw = fm.horizontalAdvance(self.label_text)
        th = fm.height()

        box = QRectF(
            self.label_pos.x() - tw / 2.0 - 4,
            self.label_pos.y() - th / 2.0 - 2,
            tw + 8,
            th + 4
        )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawRoundedRect(box, 3, 3)

        painter.setPen(color)
        painter.drawText(box, Qt.AlignCenter, self.label_text)


class LegendItem(QGraphicsItem):
    """Overlay legend drawn in top-right of view, ignoring transformations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        self.setZValue(100)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, 120, 130)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#CCCCCC"), 1))
        painter.setBrush(QBrush(QColor(255, 255, 255, 230)))
        painter.drawRoundedRect(0, 0, 120, 130, 4, 4)

        font = QFont("Segoe UI", 8)
        painter.setFont(font)

        entries = [
            ("Junction", QColor("#87CEEB"), "node"),
            ("Tank", QColor("#FFD700"), "node"),
            ("Reservoir", QColor("#FA8072"), "node"),
            ("Pipe", QColor("#333333"), "pipe"),
            ("Pump", QColor("#DC143C"), "pump"),
        ]

        y = 10
        for label, color, kind in entries:
            if kind == "node":
                painter.setPen(QPen(QColor("#000000"), 1))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(12, y + 2, 10, 10)
            elif kind == "pipe":
                painter.setPen(QPen(color, 2, Qt.SolidLine))
                painter.drawLine(8, y + 7, 26, y + 7)
            elif kind == "pump":
                painter.setPen(QPen(color, 2, Qt.DashLine))
                painter.drawLine(8, y + 7, 26, y + 7)

            painter.setPen(QColor("#000000"))
            painter.drawText(34, y + 12, label)
            y += 24


# ---------------------------------------------------------------------------
# Custom View Widget
# ---------------------------------------------------------------------------


class NetworkGraphicsView(QGraphicsView):
    """QGraphicsView with smooth wheel zoom around cursor and hand drag panning."""

    def __init__(self, scene: QGraphicsScene, graph_view: "GraphView", parent=None):
        super().__init__(scene, parent)
        self._graph_view = graph_view
        self.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        self.scale(factor, factor)
        self._graph_view.update_legend_position()

    def scrollContentsBy(self, dx: int, dy: int):
        super().scrollContentsBy(dx, dy)
        try:
            self._graph_view.update_legend_position()
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self._graph_view._apply_fit_if_pending()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._graph_view._apply_fit_if_pending()
        try:
            self._graph_view.update_legend_position()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main GraphView Widget
# ---------------------------------------------------------------------------


class GraphView(QWidget):
    """Widget displaying the directed water network graph using QGraphicsScene/View."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pos: Dict[str, Tuple[float, float]] = {}
        self._highlight_ids: Set[str] = set()
        self._current_network = None
        self._last_drawn_node_count = 0
        self._pending_fit = True

        self._init_ui()

    def showEvent(self, event):
        super().showEvent(event)
        self._apply_fit_if_pending()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_fit_if_pending()

    def _is_viewport_valid(self) -> bool:
        vp = self.view.viewport()
        return self.isVisible() and vp.width() > 50 and vp.height() > 50

    def _apply_fit_if_pending(self):
        if self._pending_fit and self._is_viewport_valid():
            self.fit_in_view()
            self._pending_fit = False

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Top Control Bar
        top_bar = QHBoxLayout()
        self.relayout_btn = QPushButton("Re-layout")
        self.relayout_btn.setToolTip("Recalculate layout for all nodes")
        self.relayout_btn.clicked.connect(self._on_relayout)
        top_bar.addWidget(self.relayout_btn)

        self.fit_btn = QPushButton("Fit")
        self.fit_btn.setToolTip("Fit all network elements in view")
        self.fit_btn.clicked.connect(self.fit_in_view)
        top_bar.addWidget(self.fit_btn)

        self.save_img_btn = QPushButton("Save image...")
        self.save_img_btn.setToolTip("Export current network drawing to PNG image")
        self.save_img_btn.clicked.connect(self._on_save_image)
        top_bar.addWidget(self.save_img_btn)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Graphics Scene and View
        self.scene = QGraphicsScene(self)
        self.view = NetworkGraphicsView(self.scene, self, self)
        layout.addWidget(self.view)

        self.legend_item = LegendItem()
        self.scene.addItem(self.legend_item)
        self.legend_item.setVisible(False)

        self.hint_item: Optional[QGraphicsSimpleTextItem] = None
        self._show_empty_hint()

    def _show_empty_hint(self):
        self.scene.clear()
        self.hint_item = QGraphicsSimpleTextItem("Add nodes and pipes to view network graph")
        self.hint_item.setFont(QFont("Segoe UI", 12))
        self.hint_item.setBrush(QBrush(QColor("#888888")))
        br = self.hint_item.boundingRect()
        self.hint_item.setPos(-br.width() / 2.0, -br.height() / 2.0)
        self.scene.addItem(self.hint_item)

        self.legend_item = LegendItem()
        self.scene.addItem(self.legend_item)
        self.legend_item.setVisible(False)

    def _on_relayout(self):
        self._pos.clear()
        self._pending_fit = True
        if self._current_network:
            self.draw_network(self._current_network)

    def _on_save_image(self):
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Network Image", "network.png", "PNG Images (*.png)"
        )
        if path_str:
            self.export_image(path_str)

    def get_positions(self) -> Dict[str, Tuple[float, float]]:
        """Return current canvas node positions in model space [-1, 1]."""
        return dict(self._pos)

    def set_positions(self, pos: Dict[str, Tuple[float, float]]) -> None:
        """Set canvas node positions in model space and refresh drawing."""
        self._pos = dict(pos) if pos else {}
        self._pending_fit = True
        if pos and self._current_network:
            self.draw_network(self._current_network)

    def highlight(self, ids: List[str]) -> None:
        """Highlight specified node/pipe IDs with a red outline / thick red line."""
        self._highlight_ids = set(ids)
        for item in self.scene.items():
            if isinstance(item, NodeItem):
                item.set_highlighted(item.node_id in self._highlight_ids)
            elif isinstance(item, PipeItem):
                item.set_highlighted(item.pipe_id in self._highlight_ids)

    def clear_highlight(self) -> None:
        """Clear all active graph highlights."""
        if self._highlight_ids:
            self._highlight_ids.clear()
            for item in self.scene.items():
                if isinstance(item, (NodeItem, PipeItem)):
                    item.set_highlighted(False)

    def update_legend_position(self):
        """Keep legend pinned to the top-right corner of the view without zooming."""
        try:
            if not self._current_network or not self._current_network.nodes:
                if hasattr(self, "legend_item") and self.legend_item:
                    self.legend_item.setVisible(False)
                return
            if hasattr(self, "legend_item") and self.legend_item:
                self.legend_item.setVisible(True)
                vw = self.view.viewport().width()
                if vw <= 50:
                    return
                target_scene_pt = self.view.mapToScene(max(10, vw - 135), 15)
                self.legend_item.setPos(target_scene_pt)
        except (RuntimeError, AttributeError):
            pass

    def fit_in_view(self, margin: float = 40.0):
        """Fit all graph elements nicely in the viewport with margin."""
        items = [it for it in self.scene.items() if isinstance(it, (NodeItem, PipeItem))]
        if not items:
            return
        rect = items[0].sceneBoundingRect()
        for it in items[1:]:
            rect = rect.united(it.sceneBoundingRect())
        if not rect.isEmpty():
            self.view.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio)
            self.update_legend_position()

    def render_to_image(self, scale: float = 2.0, margin: float = 24.0) -> QImage:
        """Render the network graph cropped to content plus margin on a white background."""
        nodes = [it for it in self.scene.items() if isinstance(it, NodeItem)]
        pipes = [it for it in self.scene.items() if isinstance(it, PipeItem)]
        graph_items = nodes + pipes

        if not graph_items:
            rect = self.hint_item.sceneBoundingRect() if self.hint_item else QRectF(-150, -50, 300, 100)
            export_rect = rect.adjusted(-margin, -margin, margin, margin)
            w = max(100, int(round(export_rect.width() * scale)))
            h = max(60, int(round(export_rect.height() * scale)))
            image = QImage(w, h, QImage.Format_ARGB32)
            image.fill(QColor("white"))
            painter = QPainter(image)
            painter.setRenderHints(
                QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
            )
            self.scene.render(painter, target=QRectF(0, 0, w, h), source=export_rect)
            painter.end()
            return image

        graph_rect = graph_items[0].sceneBoundingRect()
        for it in graph_items[1:]:
            graph_rect = graph_rect.united(it.sceneBoundingRect())

        # Determine legend placement inside the exported image without covering nodes
        lw = self.legend_item.boundingRect().width()
        lh = self.legend_item.boundingRect().height()

        # Try placing legend at top-right corner of graph rect
        lx = graph_rect.right() - lw
        ly = graph_rect.top()
        legend_rect = QRectF(lx, ly, lw, lh)

        # Check if this overlaps any node
        overlaps_node = any(legend_rect.intersects(n.sceneBoundingRect()) for n in nodes)
        if overlaps_node:
            lx = graph_rect.right() + 10.0
            ly = graph_rect.top()
            legend_rect = QRectF(lx, ly, lw, lh)

        self._last_export_legend_rect = legend_rect
        self.legend_item.setVisible(True)
        self.legend_item.setPos(lx, ly)

        total_content_rect = graph_rect.united(legend_rect)
        export_rect = total_content_rect.adjusted(-margin, -margin, margin, margin)

        w = int(round(export_rect.width() * scale))
        h = int(round(export_rect.height() * scale))

        image = QImage(w, h, QImage.Format_ARGB32)
        image.fill(QColor("white"))

        painter = QPainter(image)
        painter.setRenderHints(
            QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform
        )
        self.scene.render(painter, target=QRectF(0, 0, w, h), source=export_rect)
        painter.end()

        # Restore legend position for view
        self.update_legend_position()
        return image

    def export_image(self, file_path: str | Path, *args, scale: float = 2.0, margin: float = 24.0, **kwargs) -> bool:
        """Export the cropped network graph to a PNG image."""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        image = self.render_to_image(scale=scale, margin=margin)
        return image.save(str(file_path), "PNG")

    save_image = export_image

    def draw_network(self, network):
        """Draw the given Network instance on the QGraphicsScene."""
        is_first_draw = (
            self._current_network is None
            or self._current_network is not network
            or self._last_drawn_node_count == 0
        )
        if is_first_draw:
            self._pending_fit = True

        self._current_network = network
        self._last_drawn_node_count = len(network.nodes)

        if not network.nodes:
            self._show_empty_hint()
            self._pending_fit = True
            return

        self.scene.clear()

        # Build NetworkX MultiDiGraph for layout
        G = nx.MultiDiGraph()
        for n in network.nodes:
            G.add_node(n.id, type=n.type)
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

        # Map to scene coordinates
        scene_node_positions: Dict[str, QPointF] = {}
        for nid, (mx, my) in self._pos.items():
            sx, sy = model_to_scene(mx, my)
            scene_node_positions[nid] = QPointF(sx, sy)

        # Draw pipes/edges
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

                p_item = PipeItem(
                    pipe_id=data["id"],
                    start_pos=scene_node_positions[u],
                    end_pos=scene_node_positions[v],
                    has_pump=data.get("has_pump", False),
                    label_text=data.get("label", data["id"]),
                    curvature=rad,
                )
                p_item.set_highlighted(data["id"] in self._highlight_ids)
                self.scene.addItem(p_item)

        # Draw nodes
        for node in network.nodes:
            pos = scene_node_positions[node.id]
            n_item = NodeItem(node.id, node.type, pos)
            n_item.set_highlighted(node.id in self._highlight_ids)
            self.scene.addItem(n_item)

        # Legend item
        self.legend_item = LegendItem()
        self.scene.addItem(self.legend_item)
        self.legend_item.setVisible(True)

        if self._pending_fit and self._is_viewport_valid():
            self.fit_in_view()
            self._pending_fit = False
        else:
            self.update_legend_position()

    @property
    def _needs_fit(self) -> bool:
        return self._pending_fit

    @_needs_fit.setter
    def _needs_fit(self, val: bool):
        self._pending_fit = val

    # ------------------------------------------------------------------
    # Backward compatibility shim for tests
    # ------------------------------------------------------------------

    @property
    def ax(self):
        """Backward-compatibility shim allowing tests to access ax.texts."""
        view_self = self

        class _AxCompat:
            @property
            def texts(self):
                class _TextItem:
                    def __init__(self, t):
                        self._t = t

                    def get_text(self):
                        return self._t

                items = []
                for it in view_self.scene.items():
                    if isinstance(it, NodeItem):
                        items.append(_TextItem(it.node_id))
                    elif isinstance(it, QGraphicsSimpleTextItem):
                        items.append(_TextItem(it.text()))
                return items

        return _AxCompat()
