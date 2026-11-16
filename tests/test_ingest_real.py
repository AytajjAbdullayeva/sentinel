"""Group 1 against real compilers, real OSS contracts and a real Anvil node."""

from pathlib import Path

import pytest

from sentinel.chain.anvil import deploy
from sentinel.ingest import proxy
from sentinel.ingest.bytecode import identify
from sentinel.ingest.solc import compile_unit

pytestmark = [pytest.mark.fixtures]


def test_struct_selector_matches_solc(tmp_path: Path):
    (tmp_path / "S.sol").write_text(
        "pragma solidity 0.8.24;\n"
        "contract S { struct P { uint256 a; address b; }\n"
        "  function f(P[] calldata ps, bytes calldata d) external {}\n}\n")
    art = compile_unit(["S.sol"], tmp_path).get("S")  # compile_unit cross-checks against solc
    assert [f.signature for f in art.functions] == ["f((uint256,address)[],bytes)"]


def test_three_units_compile_with_expected_compilers(units):
    assert units["weth9"].compiler_version == "0.5.17"
    assert units["univ2_pair"].compiler_version == "0.5.16"
    assert units["oz_proxies"].compiler_version.startswith("0.8.")


def test_function_counts_differ_by_structure(units):
    weth = units["weth9"].get("WETH9")
    pair = units["univ2_pair"].get("UniswapV2Pair")
    assert len(weth.functions) == 11
    assert len(pair.functions) == 27
    assert {f.selector for f in weth.functions} != {f.selector for f in pair.functions}


def test_every_function_is_located_in_source(units):
    for art in (units["weth9"].get("WETH9"), units["univ2_pair"].get("UniswapV2Pair")):
        missing = [f.signature for f in art.functions if f.line is None]
        assert not missing, f"{art.name}: unlocated {missing}"


def test_assets_are_unknown_not_empty(units):
    for unit in units.values():
        for art in unit.contracts:
            assert art.assets is None and art.assets_status == "not_analyzed"


@pytest.mark.chain
def test_non_proxies_are_not_proxies(units, anvil):
    for unit, name in [("weth9", "WETH9"), ("univ2_pair", "UniswapV2Pair")]:
        addr, _ = deploy(anvil.w3, units[unit].get(name))
        report = proxy.inspect(anvil.w3, addr)
        assert report.is_proxy is False and report.implementation is None


@pytest.mark.chain
def test_eip1967_uups_proxy_detected_and_tracks_upgrade(units, anvil):
    oz = units["oz_proxies"]
    impl_v1, _ = deploy(anvil.w3, oz.get("UUPSUpgradeableMock"))
    prox, _ = deploy(anvil.w3, oz.get("ERC1967Proxy"), (impl_v1, b""))

    report = proxy.inspect(anvil.w3, prox)
    assert report.is_proxy and report.standard == "EIP-1967"
    assert report.implementation == impl_v1 and report.implementation_is_uups is True
    code = bytes(anvil.w3.eth.get_code(report.implementation))
    assert "contracts/mocks/proxy/UUPSUpgradeableMock.sol:UUPSUpgradeableMock" in identify(code, oz.contracts)

    impl_v2, _ = deploy(anvil.w3, oz.get("UUPSUpgradeableMock"))
    as_uups = anvil.w3.eth.contract(address=prox, abi=oz.get("UUPSUpgradeableMock").abi)
    tx = as_uups.functions.upgradeToAndCall(impl_v2, b"").transact({"from": anvil.w3.eth.accounts[0]})
    assert anvil.w3.eth.wait_for_transaction_receipt(tx)["status"] == 1
    assert proxy.inspect(anvil.w3, prox).implementation == impl_v2 != impl_v1


@pytest.mark.chain
def test_beacon_proxy_detected(units, anvil):
    oz = units["oz_proxies"]
    impl, _ = deploy(anvil.w3, oz.get("NonUpgradeableMock"))
    beacon, _ = deploy(anvil.w3, oz.get("UpgradeableBeacon"), (impl, anvil.w3.eth.accounts[0]))
    prox, _ = deploy(anvil.w3, oz.get("BeaconProxy"), (beacon, b""))
    report = proxy.inspect(anvil.w3, prox)
    assert report.standard == "EIP-1967 beacon"
    assert report.beacon == beacon and report.implementation == impl
    assert report.implementation_is_uups is False
