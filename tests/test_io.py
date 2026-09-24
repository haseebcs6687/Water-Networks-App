"""Tests for project file serialization and deserialization (core/io.py)."""

import json
import pytest
from core.models import Network
from core.matrices import build_matrices
from core.io import save_project, load_project


def test_save_load_round_trip(tmp_path):
    net = Network()
    net.add_node("reservoir", id="R1")
    net.add_node("junction", id="J1")
    net.add_node("junction", id="J2")
    net.add_pipe("R1", "J1", id="P1")
    net.add_pipe("J1", "J2", id="P2", has_pump=True, pump_power=12.0)

    positions = {"R1": (0.0, 0.0), "J1": (1.0, 2.0), "J2": (3.0, 4.0)}
    file_path = tmp_path / "test_net.wnet"

    save_project(file_path, net, positions)
    assert file_path.is_file()

    loaded_net, loaded_pos = load_project(file_path)

    # Check structure match
    assert len(loaded_net.nodes) == 3
    assert len(loaded_net.pipes) == 2
    assert loaded_pos == positions

    # Check matrix identity before mutating loaded_net
    orig_res = build_matrices(net.to_dict())
    loaded_res = build_matrices(loaded_net.to_dict())
    assert orig_res["labels"] == loaded_res["labels"]
    assert orig_res["E_matrix"] == loaded_res["E_matrix"]
    assert orig_res["A_matrix"] == loaded_res["A_matrix"]

    # Check ID counters restored
    next_j = loaded_net.add_node("junction")
    assert next_j.id == "J3"


def test_corrupt_file(tmp_path):
    file_path = tmp_path / "corrupt.wnet"
    file_path.write_text("{ invalid json ...", encoding="utf-8")

    with pytest.raises(ValueError, match="Corrupt JSON"):
        load_project(file_path)


def test_wrong_format(tmp_path):
    file_path = tmp_path / "wrong_format.wnet"
    data = {"format": "invalid-format", "version": 1, "nodes": [], "pipes": []}
    file_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid format identifier"):
        load_project(file_path)


def test_unknown_node_in_pipe(tmp_path):
    file_path = tmp_path / "bad_node.wnet"
    data = {
        "format": "water-network",
        "version": 1,
        "nodes": [{"id": "J1", "type": "junction"}],
        "pipes": [{"id": "P1", "start": "J1", "end": "NON_EXISTENT"}],
    }
    file_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="references unknown end node"):
        load_project(file_path)
