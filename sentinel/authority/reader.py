"""Read who controls a contract from its real state.

Every value is the decoded result of a real eth_call or eth_getLogs pinned to one block, and
carries that read. Interfaces are recognised by what the contract actually answers, with sanity
checks so that a fallback function returning junk is not mistaken for a Safe or a timelock.
A read that fails yields no fact — never a guessed default.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from eth_abi import decode
from eth_utils import keccak, to_checksum_address
from web3 import Web3

from sentinel.value.model import OnchainRead


def _sel(sig: str) -> bytes:
    return keccak(text=sig)[:4]


ROLE_NAMES = {"0x" + bytes(32).hex(): "DEFAULT_ADMIN_ROLE"} | {
    "0x" + keccak(text=n).hex(): n for n in ("PROPOSER_ROLE", "EXECUTOR_ROLE", "CANCELLER_ROLE")}
ROLE_GRANTED = "0x" + keccak(text="RoleGranted(bytes32,address,address)").hex()
ROLE_REVOKED = "0x" + keccak(text="RoleRevoked(bytes32,address,address)").hex()


@dataclass
class AuthorityFact:
    kind: str  # "multisig" | "timelock" | "owner" | "role_members"
    address: str
    values: dict
    reads: list[OnchainRead] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class _Reader:
    def __init__(self, w3: Web3, address: str, block: int):
        self.w3, self.address, self.block = w3, to_checksum_address(address), block
        self.chain_id = w3.eth.chain_id

    def call(self, sig: str, types: list[str]) -> tuple[tuple, OnchainRead] | None:
        try:
            raw = bytes(self.w3.eth.call({"to": self.address, "data": _sel(sig)}, block_identifier=self.block))
            values = decode(types, raw)
        except Exception:
            return None
        return values, OnchainRead(self.chain_id, self.block, self.address, sig, "0x" + raw.hex())


def _multisig(r: _Reader) -> AuthorityFact | None:
    t, o = r.call("getThreshold()", ["uint256"]), r.call("getOwners()", ["address[]"])
    if not t or not o:
        return None
    threshold, owners = t[0][0], [to_checksum_address(a) for a in o[0][0]]
    if not owners or not 1 <= threshold <= len(owners):
        return None  # not a coherent m-of-n answer
    return AuthorityFact("multisig", r.address, {"threshold": threshold, "owners": owners,
                                                 "signers_total": len(owners)}, [t[1], o[1]])


def _timelock(r: _Reader) -> AuthorityFact | None:
    d, p = r.call("getMinDelay()", ["uint256"]), r.call("PROPOSER_ROLE()", ["bytes32"])
    if not d or not p or p[0][0] != keccak(text="PROPOSER_ROLE"):
        return None
    return AuthorityFact("timelock", r.address, {"min_delay_seconds": d[0][0]}, [d[1], p[1]])


def _owner(r: _Reader) -> AuthorityFact | None:
    got = r.call("owner()", ["address"])
    if not got:
        return None
    raw = bytes.fromhex(got[1].raw[2:])
    if len(raw) != 32 or any(raw[:12]):
        return None
    return AuthorityFact("owner", r.address, {"owner": to_checksum_address(got[0][0])}, [got[1]])


def _roles(r: _Reader) -> AuthorityFact | None:
    """Current role members, replayed from RoleGranted/RoleRevoked logs up to the pinned block."""
    logs = r.w3.eth.get_logs({"address": r.address, "fromBlock": 0, "toBlock": r.block,
                              "topics": [[ROLE_GRANTED, ROLE_REVOKED]]})
    if not logs:
        return None
    members: dict[str, set[str]] = {}
    for log in sorted(logs, key=lambda x: (x["blockNumber"], x["logIndex"])):
        role = "0x" + bytes(log["topics"][1]).hex()
        account = to_checksum_address(bytes(log["topics"][2])[12:])
        granted = "0x" + bytes(log["topics"][0]).hex() == ROLE_GRANTED
        (members.setdefault(role, set()).add if granted else members.setdefault(role, set()).discard)(account)
    named = {ROLE_NAMES.get(role, role): sorted(accts) for role, accts in members.items()}
    read = OnchainRead(r.chain_id, r.block, r.address,
                       f"eth_getLogs RoleGranted|RoleRevoked [0..{r.block}]", f"{len(logs)} logs")
    return AuthorityFact("role_members", r.address, {"roles": named}, [read])


def read_authority(w3: Web3, address: str, block: int | None = None) -> list[AuthorityFact]:
    block = w3.eth.block_number if block is None else block
    r = _Reader(w3, address, block)
    if not w3.eth.get_code(r.address, block_identifier=block):
        return []
    return [f for f in (_multisig(r), _timelock(r), _owner(r), _roles(r)) if f is not None]
