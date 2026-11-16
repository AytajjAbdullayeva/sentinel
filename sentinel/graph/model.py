"""A typed directed graph where every edge records why it exists.

An edge without provenance cannot be constructed — there is no "connect to everything" path in this
module, because `add_edge` requires a non-empty `provenance` list. Provenance items are fact ids
(Group 2), on-chain reads (Group 3) or authority-fact references, each a short string the checkpoint
can trace back to its origin.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class NodeType(str, Enum):
    ACTOR = "actor"          # an external party (e.g. "anyone")
    AUTHORITY = "authority"  # a role / owner / multisig that controls something
    CONTRACT = "contract"
    FUNCTION = "function"
    ASSET = "asset"


class EdgeType(str, Enum):
    CAN_CALL = "can_call"        # actor/authority -> function it may invoke
    CONTROLS = "controls"        # authority -> function/contract it governs
    DECLARES = "declares"        # contract -> its own function
    CALLS = "calls"              # function -> contract/function it calls externally
    DELEGATES = "delegates"      # function -> contract it delegatecalls
    DEPENDS_ON = "depends_on"    # function -> contract it reads (e.g. a price oracle)
    TRANSFERS = "transfers"      # function -> asset it can move out
    HOLDS = "holds"             # contract -> asset it holds


@dataclass(frozen=True)
class Node:
    id: str
    type: NodeType
    label: str
    attrs: tuple = ()  # frozen (key, value) pairs for hashability


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    type: EdgeType
    provenance: tuple[str, ...]
    weight: float = 1.0
    attrs: tuple = ()

    @property
    def key(self) -> tuple[str, str, str]:
        return self.src, self.dst, self.type.value


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[tuple[str, str, str], Edge] = field(default_factory=dict)
    _adj: dict[str, list[Edge]] = field(default_factory=dict)

    def add_node(self, node: Node) -> Node:
        existing = self.nodes.get(node.id)
        if existing and existing.type != node.type:
            raise ValueError(f"node {node.id} already exists as {existing.type}, not {node.type}")
        self.nodes.setdefault(node.id, node)
        self._adj.setdefault(node.id, [])
        return self.nodes[node.id]

    def add_edge(self, src: str, dst: str, type: EdgeType, provenance: list[str],
                 weight: float = 1.0, attrs: tuple = ()) -> Edge:
        if not provenance:
            raise ValueError(f"refusing to add {type.value} {src}->{dst} with no provenance")
        if src not in self.nodes or dst not in self.nodes:
            raise KeyError(f"both endpoints must exist before adding an edge: {src}->{dst}")
        key = (src, dst, type.value)
        if key in self.edges:  # merge provenance rather than duplicate the edge
            merged = tuple(dict.fromkeys(self.edges[key].provenance + tuple(provenance)))
            edge = Edge(src, dst, type, merged, min(self.edges[key].weight, weight), attrs or self.edges[key].attrs)
            self.edges[key] = edge
            self._adj[src] = [edge if e.key == key else e for e in self._adj[src]]
            return edge
        edge = Edge(src, dst, type, tuple(provenance), weight, attrs)
        self.edges[key] = edge
        self._adj[src].append(edge)
        return edge

    def out_edges(self, node_id: str) -> list[Edge]:
        return list(self._adj.get(node_id, []))

    def nodes_of(self, node_type: NodeType) -> list[Node]:
        return [n for n in self.nodes.values() if n.type == node_type]

    def to_dict(self) -> dict:
        return {
            "nodes": [{"id": n.id, "type": n.type.value, "label": n.label, "attrs": dict(n.attrs)}
                      for n in self.nodes.values()],
            "edges": [{"src": e.src, "dst": e.dst, "type": e.type.value,
                       "provenance": list(e.provenance), "weight": e.weight, "attrs": dict(e.attrs)}
                      for e in self.edges.values()],
        }
