"""Pinned real-world compile units used by tests and checkpoints (fetched by scripts/fetch_fixtures.sh)."""

from __future__ import annotations

from pathlib import Path

from sentinel.ingest.solc import CompileResult, compile_unit

EXTERNAL = Path(__file__).resolve().parent.parent / "fixtures" / "external"

# name -> (root, entry files, pinned solc version or None to resolve from pragmas)
UNITS = {
    "weth9": (EXTERNAL / "weth", ["contracts/WETH9.sol"], None),
    "univ2_pair": (EXTERNAL / "univ2", ["contracts/UniswapV2Pair.sol", "contracts/UniswapV2Factory.sol"], None),
    "oz_proxies": (EXTERNAL / "oz", [
        "contracts/proxy/ERC1967/ERC1967Proxy.sol",
        "contracts/proxy/beacon/BeaconProxy.sol",
        "contracts/proxy/beacon/UpgradeableBeacon.sol",
        "contracts/mocks/proxy/UUPSUpgradeableMock.sol",
    ], None),
    "oz_timelock": (EXTERNAL / "oz", ["contracts/governance/TimelockController.sol"], None),
    # Safe v1.4.1 was released and deployed with solc 0.7.6; pin it to build the real artifact.
    "safe": (EXTERNAL / "safe", ["contracts/Safe.sol", "contracts/proxies/SafeProxy.sol"], "0.7.6"),
}


def available() -> bool:
    return all((root / files[0]).exists() for root, files, _ in UNITS.values())


def compile_all() -> dict[str, CompileResult]:
    return {name: compile_unit(files, root, version=version) for name, (root, files, version) in UNITS.items()}
