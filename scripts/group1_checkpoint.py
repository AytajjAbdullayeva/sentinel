"""Group 1 checkpoint: ingest three structurally different real contracts and inspect deployments."""

import json
from pathlib import Path

from sentinel import fixtures
from sentinel.chain.anvil import Anvil, deploy
from sentinel.ingest import proxy
from sentinel.ingest.bytecode import identify

OUT = Path(__file__).resolve().parent.parent / "out"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    units = fixtures.compile_all()
    summary = {}
    for unit_name, target in [("weth9", "WETH9"), ("univ2_pair", "UniswapV2Pair"),
                              ("oz_proxies", "ERC1967Proxy"), ("oz_proxies", "UUPSUpgradeableMock")]:
        art = units[unit_name].get(target)
        print(f"\n=== {art.fqn}  solc {art.compiler_version}  kind={art.kind}  functions={len(art.functions)}")
        for f in art.functions:
            loc = f"{f.source_file}:{f.line}" if f.line else "location unknown"
            print(f"  0x{f.selector}  {f.signature:<45} {f.state_mutability:<11} {loc}")
        summary[art.fqn] = {"compiler": art.compiler_version, "functions": len(art.functions),
                            "assets": art.assets, "assets_status": art.assets_status}

    with Anvil() as node:
        w3 = node.w3
        oz = units["oz_proxies"]
        weth, _ = deploy(w3, units["weth9"].get("WETH9"))
        pair, _ = deploy(w3, units["univ2_pair"].get("UniswapV2Pair"))
        impl, _ = deploy(w3, oz.get("UUPSUpgradeableMock"))
        uups_proxy, _ = deploy(w3, oz.get("ERC1967Proxy"), (impl, b""))
        plain, _ = deploy(w3, oz.get("NonUpgradeableMock"))
        beacon, _ = deploy(w3, oz.get("UpgradeableBeacon"), (plain, w3.eth.accounts[0]))
        beacon_proxy, _ = deploy(w3, oz.get("BeaconProxy"), (beacon, b""))
        deployed = {"WETH9": weth, "UniswapV2Pair": pair, "ERC1967Proxy(UUPS)": uups_proxy,
                    "BeaconProxy": beacon_proxy}
        print("\n=== proxy inspection (anvil, real eth_getStorageAt)")
        all_artifacts = [a for u in units.values() for a in u.contracts]
        for label, addr in deployed.items():
            r = proxy.inspect(w3, addr)
            impl_id = identify(bytes(w3.eth.get_code(r.implementation)), all_artifacts) if r.implementation else []
            print(f"{label:<20} {addr}  block={r.block_number} is_proxy={r.is_proxy} standard={r.standard}")
            print(f"{'':<20} implementation={r.implementation} -> {impl_id or '-'}  beacon={r.beacon}"
                  f"  uups={r.implementation_is_uups}")
            summary[label] = r.to_dict() | {"implementation_identified_as": impl_id}
        summary["_addresses"] = {"impl_uups": impl, "impl_plain": plain, "beacon": beacon}

    (OUT / "group1.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nwrote {OUT / 'group1.json'}")


if __name__ == "__main__":
    main()
