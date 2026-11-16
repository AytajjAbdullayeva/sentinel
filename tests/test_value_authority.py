"""Group 3: values have exactly two origins; authority numbers are read from real contract state."""

import ast
from decimal import Decimal
from pathlib import Path

import pytest
from eth_utils import keccak

from sentinel import scenarios
from sentinel.authority.reader import read_authority
from sentinel.value import declarations as decl
from sentinel.value.holdings import native_balance, protocol_value
from sentinel.value.model import (DECLARED_BADGE, Declared, OnchainRead, Quantity, provenance, render,
                                  total)

ONCHAIN = OnchainRead(31337, 5, "0x" + "11" * 20, "eth_getBalance", "1000")
DECL = Declared("tester", "2026-09-24T00:00:00Z", "unit test")


# ---- value model --------------------------------------------------------------------------------

def test_quantity_requires_a_source_and_decimal():
    with pytest.raises(TypeError):
        Quantity(Decimal(1), "ETH", None)
    with pytest.raises(TypeError):
        Quantity(1.5, "ETH", ONCHAIN)


def test_unknown_renders_as_unknown():
    assert render(None) == "unknown" and provenance(None) is None


def test_declared_always_shows_badge():
    assert DECLARED_BADGE in render(Quantity(Decimal(5), "USD", DECL))


def test_derived_value_is_declared_if_any_input_is_declared():
    eth = Quantity(Decimal(2), "ETH", ONCHAIN)
    usd = eth.times(Quantity(Decimal(2500), "USD", DECL), "USD")
    assert usd.amount == Decimal(5000) and usd.origin == "declared" and DECLARED_BADGE in render(usd)
    tree = provenance(usd)
    assert {i["origin"] for i in tree["inputs"]} == {"onchain", "declared"}


def test_total_is_unknown_if_any_part_is_unknown():
    a = Quantity(Decimal(1), "USD", DECL)
    assert total([a, None], "USD") is None
    assert total([], "USD") is None
    assert total([a, a], "USD").amount == Decimal(2)


def test_declarations_require_explicit_fields():
    with pytest.raises(decl.DeclarationError):
        decl.parse({"declared_by": "x", "prices_usd": {}})
    with pytest.raises(decl.DeclarationError):
        decl.parse({"declared_by": "x", "declared_at": "t", "prices_usd": {"ETH": {"usd": "1"}}})


GUARDED = ["sentinel/value", "sentinel/authority"]


def _numeric(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)


def test_no_numeric_fallbacks_in_value_or_authority_code():
    """Constitution #1: no `x or <number>`, no `.get(k, <number>)`, no numeric parameter defaults."""
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for d in GUARDED:
        for path in (root / d).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and any(map(_numeric, node.values)):
                    offenders.append(f"{path.name}:{node.lineno} `or <number>`")
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
                        and len(node.args) == 2 and _numeric(node.args[1])):
                    offenders.append(f"{path.name}:{node.lineno} `.get(k, <number>)`")
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for default in node.args.defaults + node.args.kw_defaults:
                        if default is not None and _numeric(default):
                            offenders.append(f"{path.name}:{node.lineno} numeric default in {node.name}()")
    assert not offenders, offenders


# ---- real chain ---------------------------------------------------------------------------------

pytestmark = pytest.mark.fixtures


@pytest.mark.chain
def test_onchain_value_is_pinned_to_its_block(units, anvil):
    w3 = anvil.w3
    weth = scenarios.weth_with_deposits(w3, units, [10])
    before = w3.eth.block_number
    # WETH9's fallback deposits, so plain ETH sent to it changes its balance in the next block.
    w3.eth.wait_for_transaction_receipt(w3.eth.send_transaction(
        {"from": w3.eth.accounts[2], "to": weth, "value": w3.to_wei(5, "ether")}))
    at_before, at_after = native_balance(w3, weth, before), native_balance(w3, weth, w3.eth.block_number)
    assert at_before.amount == Decimal(10) and at_before.source.block_number == before
    assert at_after.amount == Decimal(15) and at_after.source.block_number == before + 1


@pytest.mark.chain
def test_pair_tokens_are_discovered_from_storage_layout(units, anvil):
    w3 = anvil.w3
    s = scenarios.funded_pair(w3, units, 100, 400)
    pv = protocol_value(w3, "pair", {s["pair"]: units["univ2_pair"].get("UniswapV2Pair")}, decl.NONE)
    by_token = {h.token: h for h in pv.holdings}
    assert set(by_token) == {s["token_a"], s["token_b"]}
    assert by_token[s["token_a"]].amount.amount == Decimal(100)
    assert by_token[s["token_b"]].amount.amount == Decimal(400)
    # UniswapV2 sorts the pair by address, so either token may sit in token0.
    assert {"token0", "token1"} == {h.discovered_via.split("'")[1] for h in pv.holdings}
    assert pv.tvl_usd_computed is None and len(pv.unpriced_assets) == 2


@pytest.mark.chain
def test_declared_price_prices_only_the_declared_token(units, anvil):
    w3 = anvil.w3
    s = scenarios.funded_pair(w3, units, 100, 400)
    d = decl.parse({"declared_by": "t", "declared_at": "now",
                    "prices_usd": {s["token_a"]: {"usd": "2", "note": "test"}}})
    pv = protocol_value(w3, "pair", {s["pair"]: units["univ2_pair"].get("UniswapV2Pair")}, d)
    priced = {h.token: h.usd for h in pv.holdings}
    assert priced[s["token_a"]].amount == Decimal(200) and priced[s["token_a"]].origin == "declared"
    assert priced[s["token_b"]] is None and pv.tvl_usd_computed is None


@pytest.mark.chain
@pytest.mark.parametrize("n_owners,threshold", [(3, 2), (5, 3)])
def test_safe_threshold_is_read_from_state(units, anvil, n_owners, threshold):
    w3 = anvil.w3
    owners = w3.eth.accounts[1:1 + n_owners]
    s = scenarios.safe(w3, units, owners, threshold)
    facts = {f.kind: f for f in read_authority(w3, s)}
    assert facts["multisig"].values["threshold"] == threshold
    assert facts["multisig"].values["owners"] == owners
    assert facts["multisig"].reads[0].call == "getThreshold()"


@pytest.mark.chain
@pytest.mark.parametrize("delay", [172800, 3600])
def test_timelock_delay_and_roles_are_read_from_state(units, anvil, delay):
    w3 = anvil.w3
    admin, proposer, newcomer = w3.eth.accounts[0], w3.eth.accounts[1], w3.eth.accounts[4]
    tl = scenarios.timelock(w3, units, delay, [proposer], [w3.eth.accounts[2]], admin)
    facts = {f.kind: f for f in read_authority(w3, tl)}
    assert facts["timelock"].values["min_delay_seconds"] == delay
    assert facts["role_members"].values["roles"]["PROPOSER_ROLE"] == [proposer]

    art = units["oz_timelock"].get("TimelockController")
    c = w3.eth.contract(address=tl, abi=art.abi)
    tx = c.functions.grantRole(keccak(text="PROPOSER_ROLE"), newcomer).transact({"from": admin})
    w3.eth.wait_for_transaction_receipt(tx)
    roles = {f.kind: f for f in read_authority(w3, tl)}["role_members"].values["roles"]
    assert roles["PROPOSER_ROLE"] == sorted([proposer, newcomer])


@pytest.mark.chain
def test_non_authority_contract_yields_no_authority_facts(units, anvil):
    w3 = anvil.w3
    weth = scenarios.weth_with_deposits(w3, units, [1])
    assert read_authority(w3, weth) == []
    assert read_authority(w3, w3.eth.accounts[5]) == []  # an EOA
