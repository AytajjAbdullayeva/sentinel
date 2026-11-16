"""Match on-chain runtime code to a compiled artifact.

Immutable-reference ranges (reported by solc) are masked, and the trailing CBOR metadata blob is
stripped, because both legitimately differ between the artifact and a deployed instance.
"""

from __future__ import annotations

from sentinel.ingest.solc import ContractArtifact


def _strip_metadata(code: bytes) -> bytes:
    if len(code) < 2:
        return code
    meta_len = int.from_bytes(code[-2:], "big")
    if meta_len + 2 <= len(code):
        return code[: -(meta_len + 2)]
    return code


def _mask(code: bytearray, refs: dict) -> bytearray:
    for ranges in refs.values():
        for r in ranges:
            code[r["start"]: r["start"] + r["length"]] = b"\x00" * r["length"]
    return code


def runtime_matches(onchain: bytes, artifact: ContractArtifact) -> bool:
    expected = bytes.fromhex(artifact.deployed_bytecode)
    if not expected or len(onchain) != len(expected):
        return False
    a = _mask(bytearray(onchain), artifact.immutable_references)
    b = _mask(bytearray(expected), artifact.immutable_references)
    return _strip_metadata(bytes(a)) == _strip_metadata(bytes(b))


def identify(onchain: bytes, artifacts: list[ContractArtifact]) -> list[str]:
    return [a.fqn for a in artifacts if runtime_matches(onchain, a)]
