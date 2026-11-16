"""Proxy detection by reading real EIP-1967 / EIP-1822 storage slots from a chain.

A proxy verdict is only ever produced for a deployed address. Source alone never yields one.
Every read records chain id, block number, slot and the raw 32-byte word.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from eth_utils import keccak, to_checksum_address
from web3 import Web3


def _eip1967_slot(label: str) -> int:
    return int.from_bytes(keccak(text=label), "big") - 1


IMPLEMENTATION_SLOT = _eip1967_slot("eip1967.proxy.implementation")
ADMIN_SLOT = _eip1967_slot("eip1967.proxy.admin")
BEACON_SLOT = _eip1967_slot("eip1967.proxy.beacon")
EIP1822_PROXIABLE_SLOT = int.from_bytes(keccak(text="PROXIABLE"), "big")

BEACON_IMPLEMENTATION_SELECTOR = keccak(text="implementation()")[:4]
PROXIABLE_UUID_SELECTOR = keccak(text="proxiableUUID()")[:4]


@dataclass
class SlotRead:
    name: str
    slot: str
    raw: str
    address: str | None  # low 20 bytes, only if the word is a clean, non-zero address with code


@dataclass
class ProxyReport:
    address: str
    chain_id: int
    block_number: int
    is_proxy: bool
    standard: str | None  # "EIP-1967" | "EIP-1967 beacon" | "EIP-1822" | None
    implementation: str | None
    admin: str | None
    beacon: str | None
    implementation_is_uups: bool | None  # proxiableUUID() on the implementation == EIP-1967 slot
    reads: list[SlotRead] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _word_to_address(w3: Web3, word: bytes, block: int) -> str | None:
    if int.from_bytes(word, "big") == 0 or any(word[:12]):
        return None
    addr = to_checksum_address(word[12:])
    return addr if w3.eth.get_code(addr, block_identifier=block) else None


def _call(w3: Web3, to: str, data: bytes, block: int) -> bytes | None:
    try:
        return bytes(w3.eth.call({"to": to, "data": data}, block_identifier=block))
    except Exception:  # a revert is an answer: "not supported"
        return None


def inspect(w3: Web3, address: str, block: int | None = None) -> ProxyReport:
    address = to_checksum_address(address)
    block = w3.eth.block_number if block is None else block
    reads = []
    found = {}
    for name, slot in [("eip1967.implementation", IMPLEMENTATION_SLOT), ("eip1967.admin", ADMIN_SLOT),
                       ("eip1967.beacon", BEACON_SLOT), ("eip1822.proxiable", EIP1822_PROXIABLE_SLOT)]:
        word = bytes(w3.eth.get_storage_at(address, slot, block_identifier=block))
        addr = _word_to_address(w3, word, block)
        reads.append(SlotRead(name, hex(slot), "0x" + word.hex(), addr))
        found[name] = addr

    implementation, standard = found["eip1967.implementation"], None
    if implementation:
        standard = "EIP-1967"
    elif found["eip1967.beacon"]:
        standard = "EIP-1967 beacon"
        ret = _call(w3, found["eip1967.beacon"], BEACON_IMPLEMENTATION_SELECTOR, block)
        implementation = _word_to_address(w3, ret, block) if ret and len(ret) == 32 else None
    elif found["eip1822.proxiable"]:
        standard = "EIP-1822"
        implementation = found["eip1822.proxiable"]

    uups = None
    if implementation:
        ret = _call(w3, implementation, PROXIABLE_UUID_SELECTOR, block)
        uups = ret is not None and len(ret) == 32 and int.from_bytes(ret, "big") == IMPLEMENTATION_SLOT

    return ProxyReport(address=address, chain_id=w3.eth.chain_id, block_number=block,
                       is_proxy=standard is not None, standard=standard, implementation=implementation,
                       admin=found["eip1967.admin"], beacon=found["eip1967.beacon"],
                       implementation_is_uups=uups, reads=reads)
