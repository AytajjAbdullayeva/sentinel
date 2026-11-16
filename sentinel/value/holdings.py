"""What a deployed protocol holds, read from the chain.

Discovery is real: token addresses come from the contract's own state variables, located via
solc's `storageLayout` and read with eth_getStorageAt. A referenced address counts as a token only
if it answers decimals()/symbol()/balanceOf() on-chain. USD values need a price, and a price has
exactly the two origins of `sentinel.value.model`; without one the USD value is unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from eth_abi import decode
from eth_utils import keccak, to_checksum_address
from web3 import Web3

from sentinel.ingest.solc import ContractArtifact
from sentinel.value.declarations import NATIVE, Declarations
from sentinel.value.model import OnchainRead, Quantity, render, total

_SEL = {name: keccak(text=name)[:4] for name in ("decimals()", "symbol()", "balanceOf(address)")}
_ADDRESS_LABEL_PREFIXES = ("address", "contract ")


@dataclass
class StorageAddress:
    variable: str
    address: str
    read: OnchainRead


@dataclass
class Holding:
    holder: str
    asset: str  # "ETH" or "<symbol>@<token address>"
    token: str | None  # None for native ETH
    amount: Quantity
    usd: Quantity | None
    discovered_via: str


@dataclass
class ProtocolValue:
    name: str
    chain_id: int
    block_number: int
    holdings: list[Holding] = field(default_factory=list)
    tvl_usd_computed: Quantity | None = None
    unpriced_assets: list[str] = field(default_factory=list)
    tvl_usd_declared: Quantity | None = None

    def lines(self) -> list[str]:
        out = [f"protocol {self.name}  (chain {self.chain_id}, block {self.block_number})"]
        for h in self.holdings:
            out.append(f"  holding  {render(h.amount)}")
            out.append(f"           usd = {render(h.usd)}   (discovered via {h.discovered_via})")
        reason = f"  -- unpriced: {self.unpriced_assets}" if self.unpriced_assets else ""
        out.append(f"  TVL computed = {render(self.tvl_usd_computed)}{reason}")
        out.append(f"  TVL declared = {render(self.tvl_usd_declared)}")
        return out


def _call(w3: Web3, to: str, data: bytes, block: int) -> bytes | None:
    try:
        ret = bytes(w3.eth.call({"to": to, "data": data}, block_identifier=block))
    except Exception:
        return None
    return ret or None


def native_balance(w3: Web3, holder: str, block: int) -> Quantity:
    wei = w3.eth.get_balance(holder, block_identifier=block)
    read = OnchainRead(w3.eth.chain_id, block, holder, "eth_getBalance", str(wei))
    return Quantity(Decimal(wei) / Decimal(10) ** 18, NATIVE, read)


def storage_addresses(w3: Web3, holder: str, artifact: ContractArtifact, block: int) -> list[StorageAddress]:
    """Non-zero address-typed top-level state variables, read from their real slots."""
    layout = artifact.storage_layout
    found = []
    for var in layout.get("storage", []):
        type_label = layout["types"][var["type"]]["label"]
        if not type_label.startswith(_ADDRESS_LABEL_PREFIXES):
            continue
        slot, offset = int(var["slot"]), int(var["offset"])
        word = bytes(w3.eth.get_storage_at(holder, slot, block_identifier=block))
        value = word[32 - offset - 20: 32 - offset]
        if not any(value):
            continue
        read = OnchainRead(w3.eth.chain_id, block, holder, f"storage[slot {slot}, offset {offset}] ({var['label']})",
                           "0x" + word.hex())
        found.append(StorageAddress(var["label"], to_checksum_address(value), read))
    return found


def erc20_metadata(w3: Web3, token: str, block: int) -> tuple[str, int, OnchainRead] | None:
    if not w3.eth.get_code(token, block_identifier=block):
        return None
    raw_dec, raw_sym = _call(w3, token, _SEL["decimals()"], block), _call(w3, token, _SEL["symbol()"], block)
    if raw_dec is None or raw_sym is None or len(raw_dec) != 32:
        return None
    decimals = decode(["uint8"], raw_dec)[0]
    try:
        symbol = decode(["string"], raw_sym)[0]
    except Exception:
        symbol = raw_sym[:32].rstrip(b"\x00").decode(errors="replace")  # bytes32-symbol tokens (e.g. MKR)
    read = OnchainRead(w3.eth.chain_id, block, token, "decimals()", "0x" + raw_dec.hex())
    return symbol, decimals, read


def erc20_balance(w3: Web3, token: str, holder: str, decimals: int, unit: str, block: int) -> Quantity | None:
    data = _SEL["balanceOf(address)"] + bytes(12) + bytes.fromhex(holder[2:])
    raw = _call(w3, token, data, block)
    if raw is None or len(raw) != 32:
        return None
    units = decode(["uint256"], raw)[0]
    read = OnchainRead(w3.eth.chain_id, block, token, f"balanceOf({holder})", str(units))
    return Quantity(Decimal(units) / Decimal(10) ** decimals, unit, read)


def protocol_value(w3: Web3, name: str, contracts: dict[str, ContractArtifact | None],
                   declarations: Declarations, block: int | None = None) -> ProtocolValue:
    """Holdings of every contract in `contracts` (address -> artifact, None if source unknown)."""
    block = w3.eth.block_number if block is None else block
    pv = ProtocolValue(name, w3.eth.chain_id, block, tvl_usd_declared=declarations.tvl(name))
    for holder, artifact in contracts.items():
        holder = to_checksum_address(holder)
        eth = native_balance(w3, holder, block)
        if eth.amount:
            pv.holdings.append(_priced(Holding(holder, NATIVE, None, eth, None, "eth_getBalance"), declarations))
        if artifact is None:
            continue
        for ref in storage_addresses(w3, holder, artifact, block):
            meta = erc20_metadata(w3, ref.address, block)
            if meta is None:
                continue
            symbol, decimals, _ = meta
            unit = f"{symbol}@{ref.address}"
            bal = erc20_balance(w3, ref.address, holder, decimals, unit, block)
            if bal is not None and bal.amount:
                via = f"state variable '{ref.variable}' ({ref.read.call})"
                pv.holdings.append(_priced(Holding(holder, unit, ref.address, bal, None, via), declarations))
    pv.unpriced_assets = [h.asset for h in pv.holdings if h.usd is None]
    pv.tvl_usd_computed = total([h.usd for h in pv.holdings], "USD")
    return pv


def _priced(h: Holding, declarations: Declarations) -> Holding:
    price = declarations.price(NATIVE if h.token is None else h.token)
    h.usd = h.amount.times(price, "USD") if price is not None else None
    return h
