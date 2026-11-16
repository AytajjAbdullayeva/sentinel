"""Chain-backed API operations: real Anvil simulation and monitoring.

These are real (a local EVM is spun up, real transactions are sent, feasibility/profit come from real
receipts). They are scenario-scoped because a faithful exploit strategy only exists for the built-in
reconstructions (Group 5); arbitrary uploaded source cannot be auto-deployed/auto-exploited, so those
requests are answered honestly with 'no deployment harness' rather than a faked result.
"""

from __future__ import annotations

from decimal import Decimal

from sentinel.chain.anvil import Anvil
from sentinel.graph import attack, reconstruct
from sentinel.graph.builder import ANYONE, build
from sentinel.graph.paths import shortest_path
from sentinel.monitor.watcher import Monitor
from sentinel.scoring import assemble as score_assemble, config as scfg
from sentinel.scoring.engine import score
from sentinel.sim import engine, exploits
from sentinel.value.model import Declared, Quantity
from eth_utils import keccak

SCENARIOS = {
    "reentrancy": (reconstruct.reentrancy, exploits.reentrancy),
    "oracle": (reconstruct.oracle, exploits.oracle_manipulation),
}


class UnknownScenario(ValueError):
    pass


def _eth_path(graph):
    for sink in attack.asset_sinks(graph):
        if graph.nodes[sink].label == "ETH" and (p := shortest_path(graph, ANYONE, sink)):
            return p
    return None


def run_simulation(scenario: str, patched: bool, eth_price_usd: str | None = None) -> dict:
    if scenario not in SCENARIOS:
        raise UnknownScenario(scenario)
    recon_builder, exploit_builder = SCENARIOS[scenario]
    with Anvil() as node:
        w3 = node.w3
        recon = recon_builder(w3)
        graph = build(recon.analysis, recon.context)
        sc = exploit_builder(w3, patched=patched)
        sim = engine.run(w3, sc.attacker_addresses, sc.steps)
        result = {
            "scenario": scenario, "variant": "patched" if patched else "vulnerable",
            "feasible": sim.feasible, "reason": sim.reason,
            "profit_wei": sim.attacker_profit_wei, "profit_eth": sim.attacker_profit_wei / 10**18,
            "steps": [vars(s) for s in sim.steps],
            "score": None,
        }
        if eth_price_usd is not None:
            price = Quantity(Decimal(str(eth_price_usd)), "USD",
                             Declared("api-request", "runtime", "caller-declared ETH price"))
            path = _eth_path(graph)
            sr = score(score_assemble.from_pipeline(scenario, graph, path, sim, price, "declared"),
                       scfg.load())
            result["score"] = sr.to_dict()
    return result


def run_monitor_demo() -> dict:
    """Deploy a UUPS proxy + a timelock on Anvil, perform a real upgrade and role grant, report drift."""
    from sentinel import fixtures
    from sentinel.chain.anvil import deploy
    compiled = fixtures.compile_all()
    oz, tl_art = compiled["oz_proxies"], compiled["oz_timelock"].get("TimelockController")
    with Anvil() as node:
        w3 = node.w3
        admin, newcomer = w3.eth.accounts[0], w3.eth.accounts[4]
        impl_v1, _ = deploy(w3, oz.get("UUPSUpgradeableMock"))
        prox, _ = deploy(w3, oz.get("ERC1967Proxy"), (impl_v1, b""))
        tl, _ = deploy(w3, tl_art, (3600, [admin], [admin], admin))
        mon = Monitor(w3, [prox, tl])
        baseline = mon.baseline()
        quiet = [d.to_dict() for d in mon.poll()]
        impl_v2, _ = deploy(w3, oz.get("UUPSUpgradeableMock"))
        as_uups = w3.eth.contract(address=prox, abi=oz.get("UUPSUpgradeableMock").abi)
        w3.eth.wait_for_transaction_receipt(
            as_uups.functions.upgradeToAndCall(impl_v2, b"").transact({"from": admin}))
        c = w3.eth.contract(address=tl, abi=tl_art.abi)
        w3.eth.wait_for_transaction_receipt(
            c.functions.grantRole(keccak(text="PROPOSER_ROLE"), newcomer).transact({"from": admin}))
        drift = [d.to_dict() for d in mon.poll()]
    return {"baseline_block": baseline["block"], "quiet_poll": quiet, "drift": drift}
