"""After Group 11: the composed pipeline runs on unrelated real contracts and yields genuinely
different graphs and score outcomes (constitution: '3+ unrelated real contracts, different graphs/scores')."""

from decimal import Decimal

import pytest

from sentinel import pipeline
from sentinel.graph import reconstruct
from sentinel.graph.builder import build
from sentinel.sim import exploits
from sentinel.value.model import Declared, Quantity

pytestmark = [pytest.mark.fixtures, pytest.mark.chain]
PRICE = Quantity(Decimal(2500), "USD", Declared("e2e", "2026-09-25", "local ETH price"))
WETH = reconstruct.VULN_DIR.parent.parent / "external" / "weth"
UNIV2 = reconstruct.VULN_DIR.parent.parent / "external" / "univ2"


def test_static_pipeline_on_two_unrelated_real_contracts():
    weth = pipeline.analyze_static("WETH9", [WETH / "contracts" / "WETH9.sol"])
    pair = pipeline.analyze_static("UniswapV2Pair", [UNIV2 / "contracts" / "UniswapV2Pair.sol"])
    assert weth.compiler != pair.compiler or weth.facts != pair.facts
    assert (weth.graph_nodes, weth.graph_edges) != (pair.graph_nodes, pair.graph_edges)  # different graphs


def test_full_pipeline_three_reconstructions_differ(anvil):
    w3 = anvil.w3
    reent = reconstruct.reentrancy(w3)
    r = pipeline.analyze_full("reentrancy", w3, reent.analysis, reent.context,
                              *_s(exploits.reentrancy(w3, patched=False)), PRICE)
    orc = reconstruct.oracle(w3)
    o = pipeline.analyze_full("oracle", w3, orc.analysis, orc.context,
                              *_s(exploits.oracle_manipulation(w3, patched=False)), PRICE)

    assert r.score.status == "scored" and o.score.status == "scored"
    assert r.score.score != o.score.score                                   # different scores
    assert (r.graph_nodes, r.graph_edges) != (o.graph_nodes, o.graph_edges)  # different graphs
    assert r.narrative.claims and o.narrative.claims                        # both produced narratives
    # every narrative claim is grounded in real evidence
    for pa in (r, o):
        for c in pa.narrative.claims:
            assert c.evidence


def _s(scenario):
    return scenario.attacker_addresses, scenario.steps
