"""User-declared inputs, loaded from an explicit JSON file.

Format:
{
  "declared_by": "who is making these declarations",
  "declared_at": "ISO-8601 timestamp",
  "prices_usd": {"ETH": {"usd": "2500", "note": "..."},
                 "0x<checksummed token address>": {"usd": "1.00", "note": "..."}},
  "tvl_usd":    {"<protocol name>": {"usd": "5000000", "note": "..."}}
}
Prices are keyed by "ETH" (native) or by exact token address — never by symbol, because two
different tokens can share a symbol. Every field is required; a missing field is an error, not a default.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from eth_utils import to_checksum_address

from sentinel.value.model import Declared, Quantity

NATIVE = "ETH"


class DeclarationError(ValueError):
    pass


@dataclass
class Declarations:
    prices_usd: dict[str, Quantity] = field(default_factory=dict)
    tvl_usd: dict[str, Quantity] = field(default_factory=dict)

    def price(self, asset_key: str) -> Quantity | None:
        return self.prices_usd.get(asset_key)

    def tvl(self, protocol: str) -> Quantity | None:
        return self.tvl_usd.get(protocol)


def _entry(raw: dict, what: str, who: str, when: str) -> Quantity:
    for key in ("usd", "note"):
        if key not in raw:
            raise DeclarationError(f"{what}: missing '{key}'")
    return Quantity(Decimal(str(raw["usd"])), "USD", Declared(who, when, raw["note"]))


def _price_key(key: str) -> str:
    return NATIVE if key == NATIVE else to_checksum_address(key)


def parse(data: dict) -> Declarations:
    for key in ("declared_by", "declared_at"):
        if not data.get(key):
            raise DeclarationError(f"missing '{key}'")
    who, when = data["declared_by"], data["declared_at"]
    return Declarations(
        prices_usd={_price_key(k): _entry(v, f"price {k}", who, when) for k, v in data.get("prices_usd", {}).items()},
        tvl_usd={k: _entry(v, f"tvl {k}", who, when) for k, v in data.get("tvl_usd", {}).items()},
    )


def load(path: Path) -> Declarations:
    return parse(json.loads(Path(path).read_text()))


NONE = Declarations()
