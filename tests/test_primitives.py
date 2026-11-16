"""Pure checks: Keccak (not NIST SHA-3), selector canonicalisation, EIP slot constants, pragma resolution."""

import hashlib

import pytest
from eth_utils import keccak

from sentinel.ingest import pragma, proxy
from sentinel.ingest.selectors import SelectorMismatch, cross_check, selector, signature


def test_keccak_is_not_nist_sha3():
    assert keccak(b"").hex() == "c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert hashlib.sha3_256(b"").hexdigest() != keccak(b"").hex()


@pytest.mark.parametrize("sig,sel", [
    ("transfer(address,uint256)", "a9059cbb"),
    ("approve(address,uint256)", "095ea7b3"),
    ("deposit()", "d0e30db0"),
    ("withdraw(uint256)", "2e1a7d4d"),
])
def test_known_selectors(sig, sel):
    assert selector(sig) == sel


def test_tuple_signature_canonicalisation():
    entry = {"type": "function", "name": "f", "inputs": [
        {"type": "tuple[]", "components": [{"type": "uint256"}, {"type": "address"}]},
        {"type": "bytes"},
    ]}
    assert signature(entry) == "f((uint256,address)[],bytes)"


def test_cross_check_rejects_mismatch():
    with pytest.raises(SelectorMismatch):
        cross_check({"deposit()": "deadbeef"}, {"deposit()": "d0e30db0"}, "X")


def test_eip_slot_constants():
    assert hex(proxy.IMPLEMENTATION_SLOT) == "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    assert hex(proxy.ADMIN_SLOT) == "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
    assert hex(proxy.BEACON_SLOT) == "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
    assert hex(proxy.EIP1822_PROXIABLE_SLOT) == "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7"


AVAILABLE = ["0.4.26", "0.5.16", "0.5.17", "0.6.12", "0.8.20", "0.8.24", "0.9.0"]


@pytest.mark.parametrize("src,expected", [
    ("pragma solidity =0.5.16;", "0.5.16"),
    ("pragma solidity >=0.4.22 <0.6;", "0.5.17"),
    ("pragma solidity ^0.8.20;", "0.8.24"),
    ("pragma solidity ^0.4.18;", "0.4.26"),
])
def test_pragma_resolution(src, expected):
    assert pragma.resolve([src], AVAILABLE) == expected


def test_pragma_intersection_across_files():
    assert pragma.resolve(["pragma solidity >=0.5.0;", "pragma solidity =0.5.16;"], AVAILABLE) == "0.5.16"
    with pytest.raises(ValueError):
        pragma.resolve(["pragma solidity =0.5.16;", "pragma solidity ^0.8.0;"], AVAILABLE)
