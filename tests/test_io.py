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


def test_literal_v1_json_loads_correctly_with_none_fields(tmp_path):
    # Hand-written literal v1 JSON with extra unknown keys to verify backward compatibility and tolerance
    v1_json = """{
      "format": "water-network",
      "version": 1,
      "nodes": [
        {"id": "R1", "type": "reservoir", "capacity": 1000.0, "elevation": 50.0, "extra_node_meta": 999},
        {"id": "J1", "type": "junction", "capacity": 1000.0, "elevation": 45.0}
      ],
      "pipes": [
        {"id": "P1", "start": "R1", "end": "J1", "has_pump": false, "pump_power": 0.0, "extra_pipe_meta": "test"}
      ],
      "counters": {"J": 1, "R": 1, "P": 1, "T": 0},
      "positions": {
        "R1": [10.5, 20.5],
        "J1": [30.0, 40.0]
      },
      "extra_top_level": {"ignored": true}
    }"""
    file_path = tmp_path / "legacy_v1.wnet"
    file_path.write_text(v1_json, encoding="utf-8")

    loaded_net, loaded_pos = load_project(file_path)

    assert len(loaded_net.nodes) == 2
    assert len(loaded_net.pipes) == 1

    r1 = next(n for n in loaded_net.nodes if n.id == "R1")
    j1 = next(n for n in loaded_net.nodes if n.id == "J1")
    p1 = loaded_net.pipes[0]

    # Verify new fields are None on v1 load
    assert r1.head is None
    assert j1.head is None
    assert p1.length is None
    assert p1.diameter is None
    assert p1.roughness is None

    # Verify positions and existing fields loaded properly
    assert loaded_pos == {"R1": (10.5, 20.5), "J1": (30.0, 40.0)}
    assert r1.elevation == 50.0
    assert j1.elevation == 45.0


def test_v2_save_load_round_trip_preserves_new_fields(tmp_path):
    net = Network()
    net.add_node("reservoir", id="R1", elevation=20.0, head=50.0)
    net.add_node("junction", id="J1", elevation=15.0)
    net.add_pipe(
        "R1", "J1", id="P1",
        has_pump=True, pump_power=25.0,
        length=250.5, diameter=0.45, roughness=0.00015
    )

    positions = {"R1": (100.0, 200.0), "J1": (300.0, 400.0)}
    file_path = tmp_path / "v2_test.wnet"

    save_project(file_path, net, positions)

    # Inspect the saved JSON to verify format version 2
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["format"] == "water-network"
    assert data["version"] == 2
    assert data["nodes"][0]["head"] == 50.0
    assert data["pipes"][0]["length"] == 250.5
    assert data["pipes"][0]["diameter"] == 0.45
    assert data["pipes"][0]["roughness"] == 0.00015

    # Load back and verify round trip
    loaded_net, loaded_pos = load_project(file_path)
    assert loaded_pos == positions

    r_loaded = next(n for n in loaded_net.nodes if n.id == "R1")
    j_loaded = next(n for n in loaded_net.nodes if n.id == "J1")
    p_loaded = loaded_net.pipes[0]

    assert r_loaded.head == 50.0
    assert r_loaded.elevation == 20.0
    assert j_loaded.head is None
    assert j_loaded.elevation == 15.0

    assert p_loaded.id == "P1"
    assert p_loaded.has_pump is True
    assert p_loaded.pump_power == 25.0
    assert p_loaded.length == 250.5
    assert p_loaded.diameter == 0.45
    assert p_loaded.roughness == 0.00015


def test_unsupported_version_rejected(tmp_path):
    file_path = tmp_path / "unsupported_v3.wnet"
    data = {
        "format": "water-network",
        "version": 3,
        "nodes": [],
        "pipes": [],
    }
    file_path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported project file version"):
        load_project(file_path)

