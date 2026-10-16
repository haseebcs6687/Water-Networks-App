"""Tests for Qt QGraphicsScene/QGraphicsView based GraphView widget."""

import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

import pytest
from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import QApplication

from core.models import Network
from core.examples import example_paper_network, example_broken_network
from ui.graph_view import (
    GraphView, NodeItem, PipeItem, model_to_scene, scene_to_model, SCALE
)
from ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_coordinate_helpers_and_v1_positions(qapp):
    # 1. Round-trip conversion
    test_points = [(0.0, 0.0), (1.0, 1.0), (-0.5, 0.75), (0.123, -0.987)]
    for mx, my in test_points:
        sx, sy = model_to_scene(mx, my)
        assert sx == pytest.approx(mx * SCALE)
        assert sy == pytest.approx(-my * SCALE)

        rx, ry = scene_to_model(sx, sy)
        assert rx == pytest.approx(mx)
        assert ry == pytest.approx(my)

    # 2. set_positions then get_positions round-trip
    view = GraphView()
    pos_dict = {"R1": (0.2, 0.8), "J1": (-0.4, -0.6)}
    net = Network()
    net.add_node("reservoir", id="R1")
    net.add_node("junction", id="J1")
    net.add_pipe("R1", "J1", id="P1")

    view.set_positions(pos_dict)
    view.draw_network(net)
    retrieved = view.get_positions()
    assert retrieved["R1"] == (0.2, 0.8)
    assert retrieved["J1"] == (-0.4, -0.6)

    # 3. Hand-written v1 position dict (y pointing UP) produces scene positions (y negated)
    r1_item = next(it for it in view.scene.items() if isinstance(it, NodeItem) and it.node_id == "R1")
    j1_item = next(it for it in view.scene.items() if isinstance(it, NodeItem) and it.node_id == "J1")

    assert r1_item.pos().x() == pytest.approx(0.2 * SCALE)
    assert r1_item.pos().y() == pytest.approx(-0.8 * SCALE)  # negated Y

    assert j1_item.pos().x() == pytest.approx(-0.4 * SCALE)
    assert j1_item.pos().y() == pytest.approx(0.6 * SCALE)  # negated Y (-(-0.6)*300 = +180)


def test_draw_example_networks(qapp):
    view = GraphView()

    # 1. Paper example: 6 nodes, 8 pipes
    net_paper = example_paper_network()
    view.draw_network(net_paper)

    node_items = [it for it in view.scene.items() if isinstance(it, NodeItem)]
    pipe_items = [it for it in view.scene.items() if isinstance(it, PipeItem)]

    assert len(node_items) == 6
    assert len(pipe_items) == 8

    # 2. Broken example: 6 nodes, 5 pipes
    net_broken = example_broken_network()
    view.draw_network(net_broken)

    node_items = [it for it in view.scene.items() if isinstance(it, NodeItem)]
    pipe_items = [it for it in view.scene.items() if isinstance(it, PipeItem)]

    assert len(node_items) == 6
    assert len(pipe_items) == 5


def test_highlight_and_clear_highlight(qapp):
    view = GraphView()
    net = example_paper_network()
    view.draw_network(net)

    # Highlight R1 and P1
    view.highlight(["R1", "P1"])

    r1_item = next(it for it in view.scene.items() if isinstance(it, NodeItem) and it.node_id == "R1")
    j1_item = next(it for it in view.scene.items() if isinstance(it, NodeItem) and it.node_id == "J1")
    p1_item = next(it for it in view.scene.items() if isinstance(it, PipeItem) and it.pipe_id == "P1")
    p2_item = next(it for it in view.scene.items() if isinstance(it, PipeItem) and it.pipe_id == "P2")

    assert r1_item._highlighted is True
    assert j1_item._highlighted is False
    assert p1_item._highlighted is True
    assert p2_item._highlighted is False

    # Clear highlight
    view.clear_highlight()
    assert r1_item._highlighted is False
    assert p1_item._highlighted is False


def test_parallel_pipes_produce_different_paths(qapp):
    net = Network()
    net.add_node("junction", id="J1")
    net.add_node("junction", id="J2")
    # Two pipes connecting J1 and J2
    net.add_pipe("J1", "J2", id="P1")
    net.add_pipe("J1", "J2", id="P2")

    view = GraphView()
    view.draw_network(net)

    pipe_items = [it for it in view.scene.items() if isinstance(it, PipeItem)]
    assert len(pipe_items) == 2

    p1 = next(p for p in pipe_items if p.pipe_id == "P1")
    p2 = next(p for p in pipe_items if p.pipe_id == "P2")

    # The curvatures and control points must differ
    assert p1.curvature != p2.curvature
    assert p1.label_pos != p2.label_pos


def test_empty_network_shows_hint_and_zero_nodes(qapp):
    view = GraphView()
    net = Network()
    view.draw_network(net)

    node_items = [it for it in view.scene.items() if isinstance(it, NodeItem)]
    pipe_items = [it for it in view.scene.items() if isinstance(it, PipeItem)]

    assert len(node_items) == 0
    assert len(pipe_items) == 0
    assert view.hint_item is not None
    assert "Add nodes and pipes to view network graph" in view.hint_item.text()
    assert view.legend_item.isVisible() is False


def test_relayout_and_position_preservation(qapp):
    net = Network()
    net.add_node("junction", id="J1")
    net.add_node("junction", id="J2")
    net.add_pipe("J1", "J2", id="P1")

    view = GraphView()
    view.draw_network(net)

    pos_initial = view.get_positions()
    assert "J1" in pos_initial and "J2" in pos_initial
    j1_pos_before = pos_initial["J1"]
    j2_pos_before = pos_initial["J2"]

    # Add a third node J3: existing positions for J1 and J2 must be preserved
    net.add_node("junction", id="J3")
    net.add_pipe("J2", "J3", id="P2")
    view.draw_network(net)

    pos_after_add = view.get_positions()
    assert len(pos_after_add) == 3
    assert tuple(pos_after_add["J1"]) == tuple(j1_pos_before)
    assert tuple(pos_after_add["J2"]) == tuple(j2_pos_before)

    # Re-layout button clicked: all nodes get positions
    view.relayout_btn.click()
    pos_after_relayout = view.get_positions()
    assert len(pos_after_relayout) == 3
    assert "J1" in pos_after_relayout and "J2" in pos_after_relayout and "J3" in pos_after_relayout


def test_zoom_level_survives_refresh_after_edit(qapp):
    window = MainWindow()
    window.show()
    window.network = example_paper_network()
    window.refresh()

    view = window.graph_view.view
    initial_scale_x = view.transform().m11()

    # User zooms in by factor of 2
    view.scale(2.0, 2.0)
    zoomed_scale_x = view.transform().m11()
    assert pytest.approx(zoomed_scale_x, rel=1e-3) == initial_scale_x * 2.0

    # User edits a pipe parameter (triggers window.refresh())
    window._on_update_pipe("P1", {"length": 550.0})

    # Scale transform must not have reset to initial_scale_x
    scale_after_edit = view.transform().m11()
    assert pytest.approx(scale_after_edit, rel=1e-3) == zoomed_scale_x
    assert window.network.pipes[0].length == 550.0

    window.setWindowModified(False)
    window.close()


def test_fit_on_first_draw_and_deferred_tab_switch(qapp):
    window = MainWindow()
    window.resize(1280, 800)
    # Start on Matrices tab (index 1) so GraphView is hidden
    window.right_tabs.setCurrentIndex(1)
    window.show()
    qapp.processEvents()

    # Load example paper network while Matrices tab is active
    window._on_load_example(example_paper_network)
    assert window.graph_view._pending_fit is True

    # Switch to Network tab (index 0)
    window.right_tabs.setCurrentIndex(0)
    qapp.processEvents()

    # showEvent/resizeEvent should have applied fit and cleared _pending_fit
    assert window.graph_view._pending_fit is False

    # Check all nodes are inside viewport rect
    vp_rect = window.graph_view.view.viewport().rect()
    for item in window.graph_view.scene.items():
        if isinstance(item, NodeItem):
            vp_poly = window.graph_view.view.mapFromScene(item.sceneBoundingRect())
            r = vp_poly.boundingRect()
            assert r.left() >= 0
            assert r.right() <= vp_rect.width()
            assert r.top() >= 0
            assert r.bottom() <= vp_rect.height()

    # Record scale
    scale_before = window.graph_view.view.transform().m11()

    # Window resize: zoom should NOT be reset
    window.resize(1400, 900)
    qapp.processEvents()
    scale_after_resize = window.graph_view.view.transform().m11()
    assert pytest.approx(scale_after_resize, rel=1e-3) == scale_before

    # Clicking Fit should refit
    window.graph_view.fit_btn.click()
    scale_after_fit = window.graph_view.view.transform().m11()
    assert scale_after_fit != scale_after_resize

    window.setWindowModified(False)
    window.close()


def test_cropped_image_export_and_legend_non_overlap(qapp, tmp_path):
    view = GraphView()
    net = example_paper_network()
    view.draw_network(net)

    # 1. Render to image
    img = view.render_to_image(scale=2.0, margin=24.0)
    assert not img.isNull()
    w, h = img.width(), img.height()

    # 2. Check pixel size is cropped (~1240 x 1264 rather than fixed 1200x900)
    assert 1000 <= w <= 1600
    assert 1000 <= h <= 1600

    # 3. Non-white pixel fraction
    non_white = 0
    step = 4
    for y in range(0, h, step):
        for x in range(0, w, step):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                non_white += 1
    sampled_total = ((w + step - 1) // step) * ((h + step - 1) // step)
    fraction = non_white / sampled_total
    assert fraction > 0.02

    # 4. Legend present and does not overlap any node
    legend_rect = view.legend_item.sceneBoundingRect()
    node_items = [it for it in view.scene.items() if isinstance(it, NodeItem)]
    assert len(node_items) == 6
    for node in node_items:
        node_rect = node.sceneBoundingRect()
        assert not legend_rect.intersects(node_rect)

    # 5. export_image file saving
    out_file = tmp_path / "test_export.png"
    ok = view.export_image(out_file)
    assert ok is True
    assert out_file.exists() and out_file.stat().st_size > 0
