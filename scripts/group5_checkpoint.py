"""Group 5 checkpoint: reproduce 2 historical exploit patterns on a real local Anvil, vuln vs patched."""

import json
from pathlib import Path

from web3 import Web3

from sentinel.chain.anvil import Anvil
from sentinel.sim import engine, exploits

OUT = Path(__file__).resolve().parent.parent / "out"


def _run(w3, scenario):
    r = engine.run(w3, scenario.attacker_addresses, scenario.steps)
    print(f"\n--- {scenario.name} / {scenario.variant}  {scenario.addresses}")
    for s in r.steps:
        st = {1: "OK", 0: "REVERT", None: "-"}[s.status]
        print(f"    [{st:6}] {s.description}")
        print(f"             tx={s.tx_hash} gas={s.gas_used} realizes: {s.realizes}")
        if s.error:
            print(f"             error: {s.error}")
    eth = lambda wei: f"{wei / 10**18:.6f}"  # handles negatives, unlike Web3.from_wei
    print(f"    profit = {eth(r.attacker_profit_wei)} ETH  "
          f"(start {eth(r.attacker_start_wei)} -> end {eth(r.attacker_end_wei)})")
    print(f"    FEASIBLE = {r.feasible}  ({r.reason})")
    return r


def main() -> None:
    OUT.mkdir(exist_ok=True)
    report = {}
    for name, builder in [("reentrancy (TheDAO / SWC-107)", exploits.reentrancy),
                          ("oracle manipulation (bZx / Mango style)", exploits.oracle_manipulation)]:
        print(f"\n{'=' * 78}\n{name}")
        with Anvil() as node:  # fresh chain per reproduction
            vuln = _run(node.w3, builder(node.w3, patched=False))
        with Anvil() as node:
            fixed = _run(node.w3, builder(node.w3, patched=True))
        report[name] = {"vulnerable": vuln.to_dict(), "patched": fixed.to_dict()}
        assert vuln.feasible and not fixed.feasible, f"{name}: expected vuln feasible, patched infeasible"
    (OUT / "group5.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\nwrote {OUT / 'group5.json'}")


if __name__ == "__main__":
    main()
