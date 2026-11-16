"""Deploy the vulnerable reconstruction contracts and assemble a real DeployedContext for the graph.

Used by the Group 4 test and checkpoint. Everything is real: solc compiles the fixture, Slither
analyses it, the bytecode is deployed to Anvil and funded, and holdings/authority are read back.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from web3 import Web3

from sentinel.authority.reader import read_authority
from sentinel.chain.anvil import deploy
from sentinel.graph.builder import DeployedContext
from sentinel.ingest.solc import CompileResult, compile_unit
from sentinel.static.slither_analyzer import AnalysisResult, analyze
from sentinel.value.declarations import NONE
from sentinel.value.holdings import protocol_value

VULN_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "contracts" / "vuln"


@dataclass
class Reconstruction:
    name: str
    analysis: AnalysisResult
    compiled: CompileResult
    addresses: dict[str, str]
    context: DeployedContext


def _analyze(file: str) -> tuple[AnalysisResult, CompileResult]:
    path = VULN_DIR / file
    return analyze(path, root=VULN_DIR), compile_unit([file], VULN_DIR)


def _context(w3: Web3, addr_by_name: dict[str, str], artifacts: dict[str, object]) -> DeployedContext:
    holdings, authority = {}, {}
    for name, addr in addr_by_name.items():
        pv = protocol_value(w3, name, {addr: artifacts[name]}, NONE)
        holdings[name] = pv.holdings
        authority[name] = read_authority(w3, addr)
    return DeployedContext(holdings=holdings, authority=authority)


def reentrancy(w3: Web3) -> Reconstruction:
    analysis, compiled = _analyze("ReentrantVault.sol")
    art = compiled.get("ReentrantVault")
    addr, _ = deploy(w3, art)
    vault = w3.eth.contract(address=addr, abi=art.abi)
    w3.eth.wait_for_transaction_receipt(
        vault.functions.deposit().transact({"from": w3.eth.accounts[1], "value": w3.to_wei(50, "ether")}))
    ctx = _context(w3, {"ReentrantVault": addr}, {"ReentrantVault": art})
    return Reconstruction("reentrancy", analysis, compiled, {"ReentrantVault": addr}, ctx)


def oracle(w3: Web3) -> Reconstruction:
    analysis, compiled = _analyze("OracleLending.sol")
    oracle_art, pool_art = compiled.get("SpotOracle"), compiled.get("LendingPool")
    oracle_addr, _ = deploy(w3, oracle_art)
    w3.eth.contract(address=oracle_addr, abi=oracle_art.abi)
    pool_addr, _ = deploy(w3, pool_art, (oracle_addr,))
    pool = w3.eth.contract(address=pool_addr, abi=pool_art.abi)
    # Fund the pool via its own payable entry point (it has no receive()), so it holds ETH to drain.
    w3.eth.wait_for_transaction_receipt(
        pool.functions.depositCollateral().transact({"from": w3.eth.accounts[0], "value": w3.to_wei(100, "ether")}))
    ctx = _context(w3, {"SpotOracle": oracle_addr, "LendingPool": pool_addr},
                   {"SpotOracle": oracle_art, "LendingPool": pool_art})
    return Reconstruction("oracle_manipulation", analysis, compiled,
                          {"SpotOracle": oracle_addr, "LendingPool": pool_addr}, ctx)


def governance(w3: Web3) -> Reconstruction:
    analysis, compiled = _analyze("GovTreasury.sol")
    art = compiled.get("GovTreasury")
    addr, _ = deploy(w3, art, (w3.eth.accounts[9],))  # governor = account 9
    w3.eth.wait_for_transaction_receipt(
        w3.eth.send_transaction({"from": w3.eth.accounts[0], "to": addr, "value": w3.to_wei(500, "ether")}))
    ctx = _context(w3, {"GovTreasury": addr}, {"GovTreasury": art})
    return Reconstruction("governance_takeover", analysis, compiled, {"GovTreasury": addr}, ctx)


def all_reconstructions(w3: Web3) -> list[Reconstruction]:
    return [reentrancy(w3), oracle(w3), governance(w3)]
