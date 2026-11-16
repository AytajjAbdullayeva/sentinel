"""Group 9: the monitor emits drift only from real on-chain events, and nothing when nothing changes."""

import pytest
from eth_utils import keccak

from sentinel.chain.anvil import deploy
from sentinel.monitor.watcher import Monitor

pytestmark = [pytest.mark.fixtures, pytest.mark.chain]


def test_no_change_yields_no_drift(units, anvil):
    w3 = anvil.w3
    oz = units["oz_proxies"]
    impl, _ = deploy(w3, oz.get("UUPSUpgradeableMock"))
    prox, _ = deploy(w3, oz.get("ERC1967Proxy"), (impl, b""))
    mon = Monitor(w3, [prox])
    mon.baseline()
    # mine an unrelated block (a plain transfer) — not an attack-surface event
    w3.eth.wait_for_transaction_receipt(
        w3.eth.send_transaction({"from": w3.eth.accounts[0], "to": w3.eth.accounts[1], "value": 1}))
    assert mon.poll() == []  # no fabricated events


def test_real_upgrade_is_detected(units, anvil):
    w3 = anvil.w3
    oz = units["oz_proxies"]
    impl_v1, _ = deploy(w3, oz.get("UUPSUpgradeableMock"))
    prox, _ = deploy(w3, oz.get("ERC1967Proxy"), (impl_v1, b""))
    mon = Monitor(w3, [prox])
    base = mon.baseline()
    assert base["implementations"][prox] == impl_v1

    impl_v2, _ = deploy(w3, oz.get("UUPSUpgradeableMock"))
    as_uups = w3.eth.contract(address=prox, abi=oz.get("UUPSUpgradeableMock").abi)
    tx = as_uups.functions.upgradeToAndCall(impl_v2, b"").transact({"from": w3.eth.accounts[0]})
    receipt = w3.eth.wait_for_transaction_receipt(tx)

    drifts = mon.poll()
    upgrades = [d for d in drifts if d.kind == "implementation_upgraded"]
    assert len(upgrades) == 1
    d = upgrades[0]
    assert d.before == impl_v1 and d.after == impl_v2
    assert d.evidence["tx_hash"] == receipt["transactionHash"].hex()  # real tx, not synthetic


def test_real_role_grant_is_detected(units, anvil):
    w3 = anvil.w3
    admin, newcomer = w3.eth.accounts[0], w3.eth.accounts[4]
    tl_art = units["oz_timelock"].get("TimelockController")
    tl, _ = deploy(w3, tl_art, (3600, [admin], [admin], admin))
    mon = Monitor(w3, [tl])
    mon.baseline()

    c = w3.eth.contract(address=tl, abi=tl_art.abi)
    role = keccak(text="PROPOSER_ROLE")
    tx = c.functions.grantRole(role, newcomer).transact({"from": admin})
    receipt = w3.eth.wait_for_transaction_receipt(tx)

    grants = [d for d in mon.poll() if d.kind == "role_granted"]
    assert any(d.after == newcomer and "PROPOSER_ROLE" in d.description for d in grants)
    assert all(d.evidence["tx_hash"] for d in grants)
    assert grants[0].evidence["tx_hash"] == receipt["transactionHash"].hex()


def test_poll_before_baseline_raises(anvil):
    with pytest.raises(RuntimeError):
        Monitor(anvil.w3, []).poll()
