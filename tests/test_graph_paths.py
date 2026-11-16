"""Pure graph + Yen's k-shortest-paths, including a cross-check against networkx as ground truth."""

import networkx as nx
import pytest

from sentinel.graph.model import EdgeType, Graph, Node, NodeType
from sentinel.graph.paths import k_shortest_paths, shortest_path


def _line(n: int) -> Graph:
    g = Graph()
    for i in range(n):
        g.add_node(Node(str(i), NodeType.CONTRACT, str(i)))
    return g


def test_add_edge_requires_provenance():
    g = _line(2)
    with pytest.raises(ValueError):
        g.add_edge("0", "1", EdgeType.CALLS, [])


def test_add_edge_requires_existing_endpoints():
    g = _line(1)
    with pytest.raises(KeyError):
        g.add_edge("0", "1", EdgeType.CALLS, ["p"])


def test_duplicate_edge_merges_provenance():
    g = _line(2)
    g.add_edge("0", "1", EdgeType.CALLS, ["a"])
    e = g.add_edge("0", "1", EdgeType.CALLS, ["b"])
    assert e.provenance == ("a", "b") and len(g.out_edges("0")) == 1


def test_shortest_path_simple():
    g = _line(3)
    g.add_edge("0", "1", EdgeType.CALLS, ["p"])
    g.add_edge("1", "2", EdgeType.CALLS, ["p"])
    p = shortest_path(g, "0", "2")
    assert p.nodes == ("0", "1", "2") and p.cost == 2.0
    assert shortest_path(g, "2", "0") is None


def test_yen_returns_distinct_ordered_paths():
    g = _line(4)
    for a, b, w in [("0", "1", 1), ("1", "3", 1), ("0", "2", 1), ("2", "3", 1), ("1", "2", 1)]:
        g.add_edge(a, b, EdgeType.CALLS, ["p"], weight=w)
    paths = k_shortest_paths(g, "0", "3", 5)
    costs = [p.cost for p in paths]
    assert costs == sorted(costs)
    assert len({p.nodes for p in paths}) == len(paths)  # all distinct
    assert paths[0].nodes == ("0", "1", "3")  # a 2-hop shortest exists


def _random_graph(seed: int, n: int = 12) -> Graph:
    import random
    rng = random.Random(seed)
    g = Graph()
    for i in range(n):
        g.add_node(Node(str(i), NodeType.CONTRACT, str(i)))
    for a in range(n):
        for b in range(n):
            if a != b and rng.random() < 0.3:
                g.add_edge(str(a), str(b), EdgeType.CALLS, ["p"], weight=rng.randint(1, 5))
    return g


@pytest.mark.parametrize("seed", range(12))
def test_yen_matches_networkx(seed):
    g = _random_graph(seed)
    nxg = nx.DiGraph()
    for e in g.edges.values():
        nxg.add_edge(e.src, e.dst, weight=e.weight)
    src, dst = "0", "5"
    ours = k_shortest_paths(g, src, dst, 6)
    if src not in nxg or dst not in nxg or not nx.has_path(nxg, src, dst):
        assert ours == []
        return
    ref = []
    for path in nx.shortest_simple_paths(nxg, src, dst, weight="weight"):
        ref.append(nx.path_weight(nxg, path, "weight"))
        if len(ref) == 6:
            break
    assert [p.cost for p in ours] == ref  # same number of paths and identical cost sequence
    for p in ours:  # every returned path is valid and loopless
        assert len(set(p.nodes)) == len(p.nodes)
        assert p.nodes[0] == src and p.nodes[-1] == dst
