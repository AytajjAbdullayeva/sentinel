"""Group 4 on real analysis + a real chain: graph topology of the three exploit reconstructions."""

import pytest

from sentinel.graph import attack, reconstruct
from sentinel.graph.builder import ANYONE, build
from sentinel.graph.model import EdgeType

pytestmark = [pytest.mark.fixtures, pytest.mark.chain]


def test_no_edge_lacks_provenance_ever(anvil):
    for r in reconstruct.all_reconstructions(anvil.w3):
        g = build(r.analysis, r.context)
        assert g.edges, r.name
        for e in g.edges.values():
            assert e.provenance, f"{r.name}: {e.key} has no provenance"


def test_reentrancy_topology(anvil):
    r = reconstruct.reentrancy(anvil.w3)
    g = build(r.analysis, r.context)
    hits = [h for h in attack.recognize(g, r.analysis) if h.pattern == "reentrancy"]
    assert hits, "expected a reentrancy hit"
    assert hits[0].where == "ReentrantVault.withdraw()"
    # anyone can reach an ETH asset through withdraw's transfer edge
    paths = attack.attacker_paths(g)
    assert any(any(e.type == EdgeType.TRANSFERS for e in p.edges)
               for ps in paths.values() for p in ps)
    assert any("reentrancy-eth" in ev for ev in hits[0].evidence)


def test_oracle_manipulation_topology(anvil):
    r = reconstruct.oracle(anvil.w3)
    g = build(r.analysis, r.context)
    dep_edges = [e for e in g.edges.values() if e.type == EdgeType.DEPENDS_ON]
    assert any("LendingPool.borrow" in g.nodes[e.src].label for e in dep_edges), "borrow should depend on the oracle"
    hits = [h for h in attack.recognize(g, r.analysis) if h.pattern == "oracle_manipulation"]
    assert hits and "borrow" in hits[0].where
    # the permissionless swap that moves the price is reachable by anyone
    swap = "fn:SpotOracle.swap(uint256)"
    assert any(e.dst == swap for e in g.out_edges(ANYONE))


def test_governance_takeover_topology(anvil):
    r = reconstruct.governance(anvil.w3)
    g = build(r.analysis, r.context)
    hits = [h for h in attack.recognize(g, r.analysis) if h.pattern == "governance_takeover"]
    assert hits, "expected a governance takeover hit"
    # withdraw is protected: anyone cannot call it directly
    withdraw = "fn:GovTreasury.withdraw(address,uint256)"
    assert not any(e.dst == withdraw for e in g.out_edges(ANYONE))
    # but an authority controls it and it transfers value
    auth_paths = attack.authority_paths(g)
    assert any(any(e.type == EdgeType.CONTROLS for e in p.edges) and
               any(e.type == EdgeType.TRANSFERS for e in p.edges)
               for ps in auth_paths.values() for p in ps)


def test_topologies_are_distinct(anvil):
    """Constitution #5: three structurally different inputs produce three different graphs."""
    recs = reconstruct.all_reconstructions(anvil.w3)
    shapes = []
    for r in recs:
        g = build(r.analysis, r.context)
        patterns = frozenset(h.pattern for h in attack.recognize(g, r.analysis))
        shapes.append((len(g.nodes), len(g.edges), patterns))
    assert len({s[2] for s in shapes}) == 3  # each recognises a different pattern set
    assert len({(s[0], s[1]) for s in shapes}) == 3  # each has a different node/edge count
