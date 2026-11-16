"""Deployment harness for checkpoints/tests: put real fixture bytecode on Anvil in a known state.

This is test setup, not analysis. The analysis modules never see these parameters; they only read
the resulting chain state.
"""

from __future__ import annotations

from web3 import Web3

from sentinel.chain.anvil import deploy
from sentinel.ingest.solc import CompileResult

ZERO = "0x0000000000000000000000000000000000000000"


def _send(w3: Web3, fn, sender: str, value: int = 0) -> dict:
    receipt = w3.eth.wait_for_transaction_receipt(fn.transact({"from": sender, "value": value}))
    if receipt["status"] != 1:
        raise RuntimeError(f"tx reverted: {receipt['transactionHash'].hex()}")
    return receipt


def weth_with_deposits(w3: Web3, units: dict[str, CompileResult], deposits_eth: list[float]) -> str:
    art = units["weth9"].get("WETH9")
    addr, _ = deploy(w3, art)
    weth = w3.eth.contract(address=addr, abi=art.abi)
    for acct, eth in zip(w3.eth.accounts[1:], deposits_eth):
        _send(w3, weth.functions.deposit(), acct, w3.to_wei(eth, "ether"))
    return addr


def funded_pair(w3: Web3, units: dict[str, CompileResult], amount_a_eth: float, amount_b_eth: float) -> dict:
    """A real UniswapV2Factory.createPair over two WETH9 tokens, with liquidity minted by account 1."""
    uni = units["univ2_pair"]
    weth_art, pair_art, factory_art = units["weth9"].get("WETH9"), uni.get("UniswapV2Pair"), uni.get("UniswapV2Factory")
    deployer, lp = w3.eth.accounts[0], w3.eth.accounts[1]
    token_a, _ = deploy(w3, weth_art)
    token_b, _ = deploy(w3, weth_art)
    factory, _ = deploy(w3, factory_art, (deployer,))  # feeToSetter
    factory_c = w3.eth.contract(address=factory, abi=factory_art.abi)
    _send(w3, factory_c.functions.createPair(token_a, token_b), deployer)
    pair = factory_c.functions.getPair(token_a, token_b).call()
    pair_c = w3.eth.contract(address=pair, abi=pair_art.abi)
    for token, eth in ((token_a, amount_a_eth), (token_b, amount_b_eth)):
        t = w3.eth.contract(address=token, abi=weth_art.abi)
        wei = w3.to_wei(eth, "ether")
        _send(w3, t.functions.deposit(), lp, wei)
        _send(w3, t.functions.transfer(pair, wei), lp)
    _send(w3, pair_c.functions.mint(lp), lp)
    return {"pair": pair, "token_a": token_a, "token_b": token_b, "factory": factory}


def safe(w3: Web3, units: dict[str, CompileResult], owners: list[str], threshold: int) -> str:
    """Real Safe v1.4.1: singleton + SafeProxy + setup()."""
    singleton, _ = deploy(w3, units["safe"].get("Safe"))
    proxy, _ = deploy(w3, units["safe"].get("SafeProxy"), (singleton,))
    s = w3.eth.contract(address=proxy, abi=units["safe"].get("Safe").abi)
    _send(w3, s.functions.setup(owners, threshold, ZERO, b"", ZERO, ZERO, 0, ZERO), w3.eth.accounts[0])
    return proxy


def timelock(w3: Web3, units: dict[str, CompileResult], min_delay: int, proposers: list[str],
             executors: list[str], admin: str) -> str:
    addr, _ = deploy(w3, units["oz_timelock"].get("TimelockController"), (min_delay, proposers, executors, admin))
    return addr
