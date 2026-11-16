"""A polling log watcher.

`Monitor.baseline()` records the current attack-surface posture (proxy implementation, owner, admin,
role members) at a block. `Monitor.poll()` fetches real logs since the last seen block via
eth_getLogs, and for every attack-surface event it re-reads the affected state and emits a DriftEvent
carrying the real transaction hash / log. With no on-chain change, poll() returns an empty list — it
never fabricates an event (the exact failure of the old codebase).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from eth_utils import keccak, to_checksum_address
from web3 import Web3

from sentinel.ingest import proxy
from sentinel.authority.reader import ROLE_NAMES

UPGRADED = "0x" + keccak(text="Upgraded(address)").hex()
ADMIN_CHANGED = "0x" + keccak(text="AdminChanged(address,address)").hex()
OWNERSHIP_TRANSFERRED = "0x" + keccak(text="OwnershipTransferred(address,address)").hex()
ROLE_GRANTED = "0x" + keccak(text="RoleGranted(bytes32,address,address)").hex()
ROLE_REVOKED = "0x" + keccak(text="RoleRevoked(bytes32,address,address)").hex()

WATCHED_TOPICS = [UPGRADED, ADMIN_CHANGED, OWNERSHIP_TRANSFERRED, ROLE_GRANTED, ROLE_REVOKED]


@dataclass
class DriftEvent:
    kind: str
    address: str
    block: int
    before: str | None
    after: str | None
    description: str
    evidence: dict = field(default_factory=dict)  # real tx hash / log reference

    def to_dict(self) -> dict:
        return asdict(self)


def _addr(topic: bytes) -> str:
    return to_checksum_address(bytes(topic)[12:])


class Monitor:
    def __init__(self, w3: Web3, addresses: list[str]):
        self.w3 = w3
        self.addresses = [to_checksum_address(a) for a in addresses]
        self.last_block: int | None = None
        self.impl: dict[str, str | None] = {}

    def baseline(self) -> dict:
        block = self.w3.eth.block_number
        for a in self.addresses:
            report = proxy.inspect(self.w3, a, block)
            self.impl[a] = report.implementation
        self.last_block = block
        return {"block": block, "implementations": dict(self.impl)}

    def poll(self) -> list[DriftEvent]:
        if self.last_block is None:
            raise RuntimeError("call baseline() before poll()")
        to_block = self.w3.eth.block_number
        events: list[DriftEvent] = []
        if to_block <= self.last_block:
            return events
        logs = self.w3.eth.get_logs({
            "address": self.addresses, "fromBlock": self.last_block + 1, "toBlock": to_block,
            "topics": [WATCHED_TOPICS],
        })
        for log in sorted(logs, key=lambda x: (x["blockNumber"], x["logIndex"])):
            events.extend(self._interpret(log))
        self.last_block = to_block
        return events

    def _interpret(self, log) -> list[DriftEvent]:
        addr = to_checksum_address(log["address"])
        topic0 = "0x" + bytes(log["topics"][0]).hex()
        block = log["blockNumber"]
        ev = {"tx_hash": log["transactionHash"].hex(), "log_index": log["logIndex"], "topic0": topic0}

        if topic0 == UPGRADED:
            after = _addr(log["topics"][1])
            before = self.impl.get(addr)
            self.impl[addr] = after
            return [DriftEvent("implementation_upgraded", addr, block, before, after,
                               f"proxy implementation changed to {after}", ev)]
        if topic0 == ADMIN_CHANGED:
            data = bytes(log["data"])
            before, after = to_checksum_address(data[12:32]), to_checksum_address(data[44:64])
            return [DriftEvent("proxy_admin_changed", addr, block, before, after,
                               f"proxy admin changed {before} -> {after}", ev)]
        if topic0 == OWNERSHIP_TRANSFERRED:
            before, after = _addr(log["topics"][1]), _addr(log["topics"][2])
            return [DriftEvent("owner_changed", addr, block, before, after,
                               f"owner changed {before} -> {after}", ev)]
        if topic0 in (ROLE_GRANTED, ROLE_REVOKED):
            role = "0x" + bytes(log["topics"][1]).hex()
            account = _addr(log["topics"][2])
            granted = topic0 == ROLE_GRANTED
            name = ROLE_NAMES.get(role, role)
            return [DriftEvent("role_granted" if granted else "role_revoked", addr, block,
                               None if granted else account, account if granted else None,
                               f"{name} {'granted to' if granted else 'revoked from'} {account}", ev)]
        return []
