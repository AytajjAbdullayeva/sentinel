"""Group 6 checkpoint: score the Group 5 exploit reproductions and a clean Group 1 contract."""

import json
from decimal import Decimal
from pathlib import Path

from sentinel.chain.anvil import Anvil, deploy
from sentinel.graph import attack, reconstruct
from sentinel.graph.builder import ANYONE, DeployedContext, build
from sentinel.graph.paths import shortest_path
from sentinel.ingest.solc import compile_unit
from sentinel.scoring import assemble, config as scfg
from sentinel.scoring.engine import score
from sentinel.sim import engine, exploits
from sentinel.static.slither_analyzer import analyze
from sentinel.value.declarations import NONE
from sentinel.value.holdings import protocol_value
from sentinel.value.model import Declared, Quantity

OUT = Path(__file__).resolve().parent.parent / "out"
WETH = reconstruct.VULN_DIR.parent.parent / "external" / "weth"
PRICE = Quantity(Decimal(2500), "USD", Declared("checkpoint", "2026-09-24", "local-chain illustrative ETH price"))


def _eth_path(g):
    for sink in attack.asset_sinks(g):
        if g.nodes[sink].label == "ETH" and (p := shortest_path(g, ANYONE, sink)):
            return p
    return None


def _print(tag, r):
    print(f"\n{tag}: {r.display}")
    for name, c in r.components.items():
        print(f"    {name} = {c.value:.4f}   <- {c.origin}")
    return r


def main() -> None:
    OUT.mkdir(exist_ok=True)
    cfg = scfg.load()
    print(f"scoring config: {cfg.version}  weights v/b/d/g = {cfg.w_value}/{cfg.w_blast}/{cfg.w_dependency}/{cfg.w_governance}")
    report, ranking = {}, []
    with Anvil() as node:
        w3 = node.w3
        rg = build(reconstruct.reentrancy(w3).analysis, reconstruct.reentrancy(w3).context)
        og = build(reconstruct.oracle(w3).analysis, reconstruct.oracle(w3).context)
        cases = [
            ("reentrancy (vulnerable)", rg, exploits.reentrancy(w3, patched=False)),
            ("oracle-manipulation (vulnerable)", og, exploits.oracle_manipulation(w3, patched=False)),
            ("reentrancy (patched)", rg, exploits.reentrancy(w3, patched=True)),
            ("oracle-manipulation (patched)", og, exploits.oracle_manipulation(w3, patched=True)),
        ]
        for tag, graph, scenario in cases:
            sim = engine.run(w3, scenario.attacker_addresses, scenario.steps)
            inp = assemble.from_pipeline(tag, graph, _eth_path(graph), sim, PRICE, "declared")
            r = _print(tag, score(inp, cfg))
            report[tag] = r.to_dict() | {"sim_feasible": sim.feasible, "profit_wei": sim.attacker_profit_wei}
            if r.status == "scored":
                ranking.append((r.score, tag))

        # A clean Group 1 contract: structural path exists, but never simulated -> insufficient data.
        art = compile_unit(["contracts/WETH9.sol"], WETH).get("WETH9")
        addr, _ = deploy(w3, art)
        weth = w3.eth.contract(address=addr, abi=art.abi)
        w3.eth.wait_for_transaction_receipt(
            weth.functions.deposit().transact({"from": w3.eth.accounts[1], "value": w3.to_wei(5, "ether")}))
        analysis = analyze(WETH / "contracts" / "WETH9.sol", root=WETH)
        pv = protocol_value(w3, "WETH9", {addr: art}, NONE)
        g = build(analysis, DeployedContext(holdings={"WETH9": pv.holdings}, authority={"WETH9": []}))
        r = _print("WETH9.withdraw (clean, not simulated)", score(
            assemble.from_pipeline("WETH9.withdraw", g, _eth_path(g), sim=None), cfg))
        report["WETH9.withdraw (clean)"] = r.to_dict()

    print("\nRANKING (scored only, high->low):")
    for s, tag in sorted(ranking, reverse=True):
        print(f"    {s:6.2f}  {tag}")
    (OUT / "group6.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\nwrote {OUT / 'group6.json'}")


if __name__ == "__main__":
    main()
