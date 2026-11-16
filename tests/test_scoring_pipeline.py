"""Group 6 end-to-end: score real reconstructions (Group 4 graph + Group 5 sim) and a clean contract."""

from decimal import Decimal

import pytest

from sentinel.graph import attack, reconstruct
from sentinel.graph.builder import ANYONE, build
from sentinel.graph.paths import shortest_path
from sentinel.ingest.solc import compile_unit
from sentinel.scoring import assemble, config as scfg
from sentinel.scoring.engine import score
from sentinel.scoring.model import ScoreInput
from sentinel.sim import engine, exploits
from sentinel.value.declarations import NONE
from sentinel.value.holdings import protocol_value
from sentinel.value.model import Declared, Quantity

pytestmark = [pytest.mark.fixtures, pytest.mark.chain]
CFG = scfg.load()
PRICE = Quantity(Decimal(2500), "USD", Declared("checkpoint", "2026-09-24", "local-chain ETH price"))


def _first_eth_path(graph):
    for sink in attack.asset_sinks(graph):
        if graph.nodes[sink].label == "ETH":
            p = shortest_path(graph, ANYONE, sink)
            if p:
                return p
    return None


def test_reentrancy_scored_higher_than_oracle_and_patched_infeasible(anvil):
    w3 = anvil.w3
    # reentrancy: real graph + real sim
    rg = build(reconstruct.reentrancy(w3).analysis, reconstruct.reentrancy(w3).context)
    r_sim = engine.run(w3, *_s(exploits.reentrancy(w3, patched=False)))
    r_in = assemble.from_pipeline("reentrancy", rg, _first_eth_path(rg), r_sim, PRICE, "declared")
    r = score(r_in, CFG)

    og = build(reconstruct.oracle(w3).analysis, reconstruct.oracle(w3).context)
    o_sim = engine.run(w3, *_s(exploits.oracle_manipulation(w3, patched=False)))
    o_in = assemble.from_pipeline("oracle", og, _first_eth_path(og), o_sim, PRICE, "declared")
    o = score(o_in, CFG)

    assert r.status == "scored" and o.status == "scored"
    assert r.score > o.score > 0
    assert o_in.depends_on_count >= 1  # oracle path really depends on a price source

    p_sim = engine.run(w3, *_s(exploits.reentrancy(w3, patched=True)))
    p = score(assemble.from_pipeline("reentrancy-patched", rg, _first_eth_path(rg), p_sim, PRICE, "declared"), CFG)
    assert p.status == "infeasible" and p.score == 0.0


def test_clean_contract_path_without_simulation_is_insufficient(anvil):
    w3 = anvil.w3
    from sentinel.chain.anvil import deploy
    art = compile_unit(["contracts/WETH9.sol"], reconstruct.VULN_DIR.parent.parent / "external" / "weth").get("WETH9")
    addr, _ = deploy(w3, art)
    weth = w3.eth.contract(address=addr, abi=art.abi)
    w3.eth.wait_for_transaction_receipt(
        weth.functions.deposit().transact({"from": w3.eth.accounts[1], "value": w3.to_wei(5, "ether")}))
    from sentinel.static.slither_analyzer import analyze
    from sentinel.graph.builder import DeployedContext
    analysis = analyze(reconstruct.VULN_DIR.parent.parent / "external" / "weth" / "contracts" / "WETH9.sol",
                       root=reconstruct.VULN_DIR.parent.parent / "external" / "weth")
    pv = protocol_value(w3, "WETH9", {addr: art}, NONE)
    g = build(analysis, DeployedContext(holdings={"WETH9": pv.holdings}, authority={"WETH9": []}))
    path = _first_eth_path(g)
    assert path is not None  # a structural path exists (anyone -> withdraw -> ETH)
    r = score(assemble.from_pipeline("WETH9.withdraw", g, path, sim=None), CFG)
    assert r.status == "insufficient_data"  # but feasibility was never established -> no number


def _s(scenario):
    return scenario.attacker_addresses, scenario.steps
