"""A quantity always carries where it came from.

There are exactly two origins:
  * OnchainRead — a real call/storage/balance read, pinned to chain id + block number;
  * Declared    — an explicit user input, always rendered with the "declared, not detected" badge.
A quantity computed from others (Derived) keeps its inputs; it counts as declared if ANY input is
declared. An absent quantity is `None` and renders as "unknown" — there is no default value.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Union

DECLARED_BADGE = "declared, not detected"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class OnchainRead:
    chain_id: int
    block_number: int
    address: str
    call: str  # e.g. "eth_getBalance", "balanceOf(address)", "storage[slot 8]"
    raw: str  # raw hex/int string exactly as returned

    origin = "onchain"


@dataclass(frozen=True)
class Declared:
    declared_by: str
    declared_at: str
    note: str

    origin = "declared"


@dataclass(frozen=True)
class Derived:
    operation: str  # "mul" | "sum"
    inputs: tuple["Quantity", ...]

    @property
    def origin(self) -> str:
        return "declared" if any(q.origin == "declared" for q in self.inputs) else "onchain"


Source = Union[OnchainRead, Declared, Derived]


@dataclass(frozen=True)
class Quantity:
    amount: Decimal
    unit: str
    source: Source

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise TypeError("amount must be a Decimal (no float rounding in values)")
        if not isinstance(self.source, (OnchainRead, Declared, Derived)):
            raise TypeError("every quantity needs an OnchainRead, Declared or Derived source")

    @property
    def origin(self) -> str:
        return self.source.origin

    def times(self, rate: "Quantity", unit: str) -> "Quantity":
        return Quantity(self.amount * rate.amount, unit, Derived("mul", (self, rate)))


def total(quantities: list["Quantity | None"], unit: str) -> "Quantity | None":
    """Sum, or None if any addend is unknown — a partial sum is never presented as a total."""
    if not quantities or any(q is None for q in quantities):
        return None
    if any(q.unit != unit for q in quantities):
        raise ValueError(f"cannot sum mixed units into {unit}: {[q.unit for q in quantities]}")
    return Quantity(sum((q.amount for q in quantities), Decimal(0)), unit, Derived("sum", tuple(quantities)))


def render(q: "Quantity | None") -> str:
    if q is None:
        return UNKNOWN
    text = f"{q.amount.normalize():f} {q.unit}"
    src = q.source
    if q.origin == "declared":
        return f"{text} [{DECLARED_BADGE}]"
    if isinstance(src, OnchainRead):
        return f"{text} [onchain: chain {src.chain_id} block {src.block_number}, {src.call} @ {src.address}]"
    return f"{text} [onchain, derived]"


def provenance(q: "Quantity | None") -> dict | None:
    """Full, JSON-able origin tree for a quantity."""
    if q is None:
        return None
    src = q.source
    base = {"amount": str(q.amount), "unit": q.unit, "origin": q.origin}
    if isinstance(src, Derived):
        return base | {"operation": src.operation, "inputs": [provenance(i) for i in src.inputs]}
    if isinstance(src, Declared):
        return base | {"badge": DECLARED_BADGE, "declared_by": src.declared_by,
                       "declared_at": src.declared_at, "note": src.note}
    return base | {"chain_id": src.chain_id, "block_number": src.block_number,
                   "address": src.address, "call": src.call, "raw": src.raw}
