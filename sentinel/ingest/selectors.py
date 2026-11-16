"""Function selectors computed from the compiler's ABI with real Keccak-256."""

from __future__ import annotations

from eth_utils import keccak


def canonical_type(param: dict) -> str:
    t = param["type"]
    if t.startswith("tuple"):
        inner = ",".join(canonical_type(c) for c in param["components"])
        return f"({inner}){t[len('tuple'):]}"
    return t


def signature(abi_entry: dict) -> str:
    args = ",".join(canonical_type(p) for p in abi_entry.get("inputs", []))
    return f"{abi_entry['name']}({args})"


def selector(sig: str) -> str:
    return keccak(text=sig)[:4].hex()


class SelectorMismatch(AssertionError):
    pass


def selectors_from_abi(abi: list[dict]) -> dict[str, str]:
    """signature -> 4-byte hex selector, for every ABI function."""
    return {signature(e): selector(signature(e)) for e in abi if e.get("type") == "function"}


def cross_check(ours: dict[str, str], solc_method_identifiers: dict[str, str], contract: str) -> None:
    """Our Keccak selectors must equal solc's own `evm.methodIdentifiers` exactly."""
    if ours != solc_method_identifiers:
        missing = set(solc_method_identifiers) ^ set(ours)
        wrong = {s for s in set(ours) & set(solc_method_identifiers) if ours[s] != solc_method_identifiers[s]}
        raise SelectorMismatch(f"{contract}: signature diff={sorted(missing)} selector diff={sorted(wrong)}")
