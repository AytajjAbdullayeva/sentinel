"""Group 3 checkpoint: two protocols with different TVL origins, plus authority read from state."""

import json
from pathlib import Path

from sentinel import fixtures, scenarios
from sentinel.authority.reader import read_authority
from sentinel.chain.anvil import Anvil
from sentinel.value import declarations
from sentinel.value.holdings import protocol_value
from sentinel.value.model import provenance

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    units = fixtures.compile_all()
    decl = declarations.load(ROOT / "fixtures" / "declarations" / "group3.json")
    report = {}
    with Anvil() as node:
        w3 = node.w3
        weth = scenarios.weth_with_deposits(w3, units, [1000, 200, 34.5])
        amm = scenarios.funded_pair(w3, units, 100, 400)
        safe = scenarios.safe(w3, units, w3.eth.accounts[5:8], 2)
        tl = scenarios.timelock(w3, units, 172800, [safe], [safe], scenarios.ZERO)

        protocols = {
            "WETH-Vault": {weth: units["weth9"].get("WETH9")},
            "DemoAMM": {amm["pair"]: units["univ2_pair"].get("UniswapV2Pair"),
                        safe: units["safe"].get("SafeProxy"),
                        tl: units["oz_timelock"].get("TimelockController")},
        }
        for name, contracts in protocols.items():
            pv = protocol_value(w3, name, contracts, decl)
            print("\n".join(pv.lines()))
            auth = [f for addr in contracts for f in read_authority(w3, addr, pv.block_number)]
            for f in auth:
                print(f"  authority {f.kind:<12} @ {f.address}: {f.values}")
                print(f"            read via {[r.call for r in f.reads]} at block {f.reads[0].block_number}")
            if not auth:
                print("  authority: none read (no multisig/timelock/owner/roles answered)")
            print()
            report[name] = {
                "block": pv.block_number,
                "holdings": [{"asset": h.asset, "amount": provenance(h.amount), "usd": provenance(h.usd),
                              "discovered_via": h.discovered_via} for h in pv.holdings],
                "tvl_usd_computed": provenance(pv.tvl_usd_computed),
                "unpriced_assets": pv.unpriced_assets,
                "tvl_usd_declared": provenance(pv.tvl_usd_declared),
                "authority": [f.to_dict() for f in auth],
            }
    (OUT / "group3.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {OUT / 'group3.json'}")


if __name__ == "__main__":
    main()
