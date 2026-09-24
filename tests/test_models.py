"""Tests for Network model additions: remove_pipe, remove_node, clear, ID reset on clear, non-contiguous matrix building."""

import pytest
from core.models import Network
from core.matrices import build_matrices
from core.checks import numeric_pencil, is_regular


def test_remove_pipe():
    net = Network()
    net.add_node("reservoir", "R1")
    net.add_node("junction", "J1")
    p1 = net.add_pipe("R1", "J1")
    assert len(net.pipes) == 1

    net.remove_pipe(p1.id)
    assert len(net.pipes) == 0

    with pytest.raises(ValueError, match="Unknown pipe ID"):
        net.remove_pipe("P99")


def test_remove_node_removes_attached_pipes():
    net = Network()
    net.add_node("reservoir", "R1")
    net.add_node("junction", "J1")
    net.add_node("junction", "J2")
    net.add_pipe("R1", "J1", id="P1")
    net.add_pipe("J1", "J2", id="P2")
    assert len(net.pipes) == 2

    # Removing J1 should remove P1 and P2
    net.remove_node("J1")
    assert len(net.nodes) == 2
    assert len(net.pipes) == 0

    with pytest.raises(ValueError, match="Unknown node ID"):
        net.remove_node("J99")


def test_clear_resets_counters():
    net = Network()
    net.add_node("reservoir")  # R1
    net.add_node("junction")   # J1
    net.add_pipe("R1", "J1")   # P1

    net.clear()
    assert len(net.nodes) == 0
    assert len(net.pipes) == 0

    # Next items created after clear must start again at J1, R1, P1
    j1 = net.add_node("junction")
    r1 = net.add_node("reservoir")
    p1 = net.add_pipe("R1", "J1")
    assert j1.id == "J1"
    assert r1.id == "R1"
    assert p1.id == "P1"


def test_individual_deletion_does_not_reuse_ids():
    net = Network()
    j1 = net.add_node("junction")  # J1
    j2 = net.add_node("junction")  # J2
    assert j1.id == "J1"
    assert j2.id == "J2"

    net.remove_node("J2")
    j3 = net.add_node("junction")  # Should be J3, NOT J2
    assert j3.id == "J3"

    p1 = net.add_pipe("J1", "J3")  # P1
    assert p1.id == "P1"
    net.remove_pipe("P1")
    p2 = net.add_pipe("J1", "J3")  # Should be P2, NOT P1
    assert p2.id == "P2"


def test_non_contiguous_ids_build_matrices_and_is_regular():
    net = Network()
    net.add_node("reservoir", "R1")
    net.add_node("junction", "J1")
    net.add_node("junction", "J2")
    net.add_node("junction", "J3")

    net.add_pipe("R1", "J1")  # P1
    net.add_pipe("J1", "J2")  # P2
    net.add_pipe("J2", "J3")  # P3

    # Remove middle junction J2 (removes P2 and P3)
    net.remove_node("J2")
    assert {n.id for n in net.nodes} == {"R1", "J1", "J3"}
    assert {p.id for p in net.pipes} == {"P1"}

    # Add a new pipe connecting J1 to J3
    net.add_pipe("J1", "J3")  # P4

    # Build matrices and verify regularity
    res = build_matrices(net.to_dict())
    assert res["K_dimension"] > 0
    E_num, A_num = numeric_pencil(res)
    assert is_regular(E_num, A_num)
