"""File I/O for saving and loading Water Network project files (.wnet)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple, Optional, Any, List

from core.models import Network


SUPPORTED_FORMAT = "water-network"
CURRENT_VERSION = 1


def save_project(
    path: str | Path,
    network: Network,
    positions: Optional[Dict[str, Tuple[float, float]]] = None
) -> None:
    """Save a network and optional canvas node positions to a JSON file.

    Parameters
    ----------
    path : str or Path
        Destination file path (.wnet).
    network : Network
        Network instance to serialize.
    positions : dict, optional
        Mapping of node IDs to (x, y) canvas coordinates.
    """
    path = Path(path)
    data = network.to_dict()

    pos_dict = {}
    if positions:
        for nid, (x, y) in positions.items():
            pos_dict[nid] = [float(x), float(y)]

    payload = {
        "format": SUPPORTED_FORMAT,
        "version": CURRENT_VERSION,
        "nodes": data["nodes"],
        "pipes": data["pipes"],
        "counters": data["counters"],
        "positions": pos_dict,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_project(path: str | Path) -> Tuple[Network, Dict[str, Tuple[float, float]]]:
    """Load a network and node positions from a JSON file.

    Parameters
    ----------
    path : str or Path
        File path to load (.wnet).

    Returns
    -------
    tuple of (Network, dict)
        Loaded Network instance and node positions mapping.

    Raises
    ------
    ValueError
        If format, version, or structure is invalid or corrupt.
    """
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"File not found: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupt JSON file {path.name}: {e}") from e
    except Exception as e:
        raise ValueError(f"Failed to read file {path.name}: {e}") from e

    if not isinstance(payload, dict):
        raise ValueError("Invalid project file: top-level JSON structure must be an object.")

    fmt = payload.get("format")
    if fmt != SUPPORTED_FORMAT:
        raise ValueError(f"Invalid format identifier {fmt!r}, expected {SUPPORTED_FORMAT!r}.")

    ver = payload.get("version")
    if ver != CURRENT_VERSION:
        raise ValueError(f"Unsupported project file version {ver!r}, expected {CURRENT_VERSION}.")

    nodes_data = payload.get("nodes")
    if not isinstance(nodes_data, list):
        raise ValueError("Invalid project file: 'nodes' must be a list.")

    pipes_data = payload.get("pipes")
    if not isinstance(pipes_data, list):
        raise ValueError("Invalid project file: 'pipes' must be a list.")

    # Validate node IDs & types
    node_ids = set()
    valid_types = {"junction", "tank", "reservoir"}
    for nd in nodes_data:
        if not isinstance(nd, dict) or "id" not in nd or "type" not in nd:
            raise ValueError("Corrupt node definition in project file.")
        nid = str(nd["id"])
        ntype = str(nd["type"])
        if nid in node_ids:
            raise ValueError(f"Duplicate node ID in project file: {nid!r}")
        if ntype not in valid_types:
            raise ValueError(f"Unknown node type {ntype!r} for node {nid!r}")
        node_ids.add(nid)

    # Validate pipe IDs & start/end references
    pipe_ids = set()
    for pd in pipes_data:
        if not isinstance(pd, dict) or "id" not in pd or "start" not in pd or "end" not in pd:
            raise ValueError("Corrupt pipe definition in project file.")
        pid = str(pd["id"])
        start = str(pd["start"])
        end = str(pd["end"])

        if pid in pipe_ids:
            raise ValueError(f"Duplicate pipe ID in project file: {pid!r}")
        if start not in node_ids:
            raise ValueError(f"Pipe {pid!r} references unknown start node {start!r}")
        if end not in node_ids:
            raise ValueError(f"Pipe {pid!r} references unknown end node {end!r}")
        pipe_ids.add(pid)

    net = Network.from_dict(payload)

    # Parse positions
    positions: Dict[str, Tuple[float, float]] = {}
    raw_pos = payload.get("positions", {})
    if isinstance(raw_pos, dict):
        for nid, coords in raw_pos.items():
            if nid in node_ids and isinstance(coords, (list, tuple)) and len(coords) == 2:
                positions[nid] = (float(coords[0]), float(coords[1]))

    return net, positions
