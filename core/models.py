"""Data models for water distribution networks.

Classes
-------
Node
    Represents a network node (Junction, Tank, Reservoir).
Pipe
    Represents a directed connection between two nodes, optionally containing a pump.
Network
    Container for nodes and pipes with validation and ID management.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict


# ---------------------------------------------------------------------------
# Core Entities
# ---------------------------------------------------------------------------


@dataclass
class Node:
    """A network node."""

    id: str
    type: str
    capacity: float = 1000.0
    elevation: float = 50.0

    _VALID_TYPES = frozenset({"junction", "tank", "reservoir"})

    def __post_init__(self) -> None:
        if self.type not in self._VALID_TYPES:
            raise ValueError(
                f"Node type must be one of {sorted(self._VALID_TYPES)}, got {self.type!r}"
            )


@dataclass
class Pipe:
    """A directed pipe connecting two nodes."""

    id: str
    start: str
    end: str
    has_pump: bool = False
    pump_power: float = 0.0


# ---------------------------------------------------------------------------
# Network container
# ---------------------------------------------------------------------------


class Network:
    """Container for nodes and pipes with validation and ID management."""

    def __init__(self) -> None:
        self._nodes: List[Node] = []
        self._pipes: List[Pipe] = []
        # Per-prefix counters (track max issued number)
        self._counters: Dict[str, int] = {"J": 0, "T": 0, "R": 0, "P": 0}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def nodes(self) -> List[Node]:
        return list(self._nodes)

    @property
    def pipes(self) -> List[Pipe]:
        return list(self._pipes)

    @property
    def counters(self) -> Dict[str, int]:
        return dict(self._counters)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _node_ids(self) -> set[str]:
        return {n.id for n in self._nodes}

    def _pipe_ids(self) -> set[str]:
        return {p.id for p in self._pipes}

    def _next_id(self, prefix: str) -> str:
        self._counters[prefix] += 1
        return f"{prefix}{self._counters[prefix]}"

    def _bump_counter(self, node_id: str) -> None:
        """Update counter so auto-generated IDs stay above *node_id*."""
        for prefix in ("J", "T", "R", "P"):
            if node_id.startswith(prefix):
                try:
                    num = int(node_id[len(prefix):])
                    if num > self._counters[prefix]:
                        self._counters[prefix] = num
                except ValueError:
                    pass
                break

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(
        self,
        type: str,  # noqa: A002
        id: Optional[str] = None,  # noqa: A002
        capacity: float = 1000.0,
        elevation: float = 50.0,
    ) -> Node:
        """Add a node and return it."""
        prefix_map = {"junction": "J", "tank": "T", "reservoir": "R"}
        prefix = prefix_map.get(type)
        if prefix is None:
            raise ValueError(
                f"Node type must be one of {sorted(prefix_map)}, got {type!r}"
            )

        if id is None:
            id = self._next_id(prefix)
        elif id in self._node_ids():
            raise ValueError(f"Node ID {id!r} is already in use.")
        else:
            self._bump_counter(id)

        node = Node(id=id, type=type, capacity=capacity, elevation=elevation)
        self._nodes.append(node)
        return node

    def add_pipe(
        self,
        start: str,
        end: str,
        id: Optional[str] = None,  # noqa: A002
        has_pump: bool = False,
        pump_power: float = 0.0,
    ) -> Pipe:
        """Add a pipe and return it."""
        if start == end:
            raise ValueError(f"Self-loop rejected: pipe from {start!r} to itself.")

        node_ids = self._node_ids()
        if start not in node_ids:
            raise ValueError(f"Unknown start node: {start!r}")
        if end not in node_ids:
            raise ValueError(f"Unknown end node: {end!r}")

        if id is None:
            id = self._next_id("P")
        elif id in self._pipe_ids():
            raise ValueError(f"Pipe ID {id!r} is already in use.")
        else:
            self._bump_counter(id)

        pipe = Pipe(id=id, start=start, end=end, has_pump=has_pump, pump_power=pump_power)
        self._pipes.append(pipe)
        return pipe

    def remove_pipe(self, pipe_id: str) -> None:
        """Remove a pipe by ID."""
        pipe = next((p for p in self._pipes if p.id == pipe_id), None)
        if pipe is None:
            raise ValueError(f"Unknown pipe ID: {pipe_id!r}")
        self._pipes.remove(pipe)

    def remove_node(self, node_id: str) -> None:
        """Remove a node by ID and any pipes attached to it."""
        node = next((n for n in self._nodes if n.id == node_id), None)
        if node is None:
            raise ValueError(f"Unknown node ID: {node_id!r}")
        self._nodes.remove(node)
        self._pipes = [p for p in self._pipes if p.start != node_id and p.end != node_id]

    def clear(self) -> None:
        """Remove all nodes and pipes and reset ID counters."""
        self._nodes.clear()
        self._pipes.clear()
        self._counters = {"J": 0, "T": 0, "R": 0, "P": 0}

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return a plain-dict representation (JSON-serialisable)."""
        return {
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "capacity": n.capacity,
                    "elevation": n.elevation,
                }
                for n in self._nodes
            ],
            "pipes": [
                {
                    "id": p.id,
                    "start": p.start,
                    "end": p.end,
                    "has_pump": p.has_pump,
                    "pump_power": p.pump_power,
                }
                for p in self._pipes
            ],
            "counters": dict(self._counters),
        }

    @classmethod
    def from_dict(cls, data: dict) -> Network:
        """Re-create a :class:`Network` from a plain-dict representation."""
        net = cls()
        for nd in data.get("nodes", []):
            net.add_node(
                type=nd["type"],
                id=nd["id"],
                capacity=nd.get("capacity", 1000.0),
                elevation=nd.get("elevation", 50.0),
            )
        for pd_ in data.get("pipes", []):
            net.add_pipe(
                start=pd_["start"],
                end=pd_["end"],
                id=pd_["id"],
                has_pump=pd_.get("has_pump", False),
                pump_power=pd_.get("pump_power", 0.0),
            )
        if "counters" in data and isinstance(data["counters"], dict):
            net._counters.update(data["counters"])
        return net

    def __repr__(self) -> str:
        return f"Network({len(self._nodes)} nodes, {len(self._pipes)} pipes)"
