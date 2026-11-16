"""Group 9 checkpoint: a real event listener. Baseline a proxy + timelock on Anvil, perform real
on-chain changes, and show the monitor reports them (with real tx hashes) and nothing otherwise."""

import json
from pathlib import Path

from eth_utils import keccak

from sentinel import fixtures
from sentinel.chain.anvil import Anvil, deploy
from sentinel.monitor.watcher import Monitor

OUT = Path(__file__).resolve().parent.parent / "out"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    units = fixtures.compile_all()
    oz, tl_art = units["oz_proxies"], units["oz_timelock"].get("TimelockController")
    report = {}
    with Anvil() as node:
        w3 = node.w3
        admin, newcomer = w3.eth.accounts[0], w3.eth.accounts[4]
        impl_v1, _ = deploy(w3, oz.get("UUPSUpgradeableMock"))
        prox, _ = deploy(w3, oz.get("ERC1967Proxy"), (impl_v1, b""))
        tl, _ = deploy(w3, tl_art, (3600, [admin], [admin], admin))

        mon = Monitor(w3, [prox, tl])
        base = mon.baseline()
        print(f"baseline @ block {base['block']}: impl({prox[:10]}...) = {base['implementations'][prox]}")

        print("\npoll with no attack-surface change:")
        w3.eth.wait_for_transaction_receipt(
            w3.eth.send_transaction({"from": admin, "to": w3.eth.accounts[1], "value": 1}))
        drifts = mon.poll()
        print(f"    drifts = {drifts}  (expected: none)")
        report["no_change_poll"] = [d.to_dict() for d in drifts]

        print("\nperforming real on-chain changes: proxy upgrade + role grant ...")
        impl_v2, _ = deploy(w3, oz.get("UUPSUpgradeableMock"))
        as_uups = w3.eth.contract(address=prox, abi=oz.get("UUPSUpgradeableMock").abi)
        up = w3.eth.wait_for_transaction_receipt(
            as_uups.functions.upgradeToAndCall(impl_v2, b"").transact({"from": admin}))
        c = w3.eth.contract(address=tl, abi=tl_art.abi)
        gr = w3.eth.wait_for_transaction_receipt(
            c.functions.grantRole(keccak(text="PROPOSER_ROLE"), newcomer).transact({"from": admin}))
        print(f"    upgrade tx = {up['transactionHash'].hex()}")
        print(f"    grantRole tx = {gr['transactionHash'].hex()}")

        print("\npoll after the changes:")
        drifts = mon.poll()
        for d in drifts:
            print(f"    [{d.kind}] {d.description}")
            print(f"        block={d.block} before={d.before} after={d.after} tx={d.evidence['tx_hash']}")
        report["after_change_poll"] = [d.to_dict() for d in drifts]
        assert not report["no_change_poll"], "no-change poll should be empty"
        kinds = {d.kind for d in drifts}
        assert "implementation_upgraded" in kinds and "role_granted" in kinds
        print("\nMONITOR OK: real events detected, no fabricated drift.")
    (OUT / "group9.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {OUT / 'group9.json'}")


if __name__ == "__main__":
    main()
