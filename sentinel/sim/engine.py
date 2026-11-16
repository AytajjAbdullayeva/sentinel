"""The execution engine. It runs steps, reads receipts, measures balances — and decides nothing else."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from web3 import Web3

# Steps are sent with an explicit gas limit so a reverting call is still mined and yields a real
# status-0 receipt, instead of being rejected client-side by gas estimation.
STEP_GAS = 5_000_000


@dataclass
class Step:
    description: str
    send: Callable[[], object]  # performs the tx, returns its hash
    realizes: str = ""          # the attack-graph edge this step realizes (Group 4)


@dataclass
class StepResult:
    description: str
    realizes: str
    tx_hash: str | None
    status: int | None  # 1 = success, 0 = revert, None = not attempted
    gas_used: int | None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == 1


@dataclass
class SimResult:
    feasible: bool
    reason: str
    attacker_profit_wei: int
    attacker_start_wei: int
    attacker_end_wei: int
    steps: list[StepResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "feasible": self.feasible, "reason": self.reason,
            "attacker_profit_wei": self.attacker_profit_wei,
            "attacker_start_wei": self.attacker_start_wei, "attacker_end_wei": self.attacker_end_wei,
            "steps": [vars(s) for s in self.steps],
        }


def _balances(w3: Web3, addresses: list[str]) -> int:
    return sum(w3.eth.get_balance(a) for a in addresses)


def run(w3: Web3, attacker_addresses: list[str], steps: list[Step]) -> SimResult:
    """Execute steps in order; stop at the first reverting step. Feasibility is measured, not assumed."""
    start = _balances(w3, attacker_addresses)
    results: list[StepResult] = []
    all_ok = True
    reason = "all steps succeeded and attacker balance increased"
    for step in steps:
        status = gas_used = tx_hash = None
        error = None
        try:
            h = step.send()
            rcpt = w3.eth.wait_for_transaction_receipt(h)
            status, gas_used = rcpt["status"], rcpt["gasUsed"]
            tx_hash = rcpt["transactionHash"].hex()
        except Exception as e:  # tx rejected before mining (e.g. predicted revert): treat as revert
            status, error = 0, f"{type(e).__name__}: {str(e)[:180]}"
        results.append(StepResult(step.description, step.realizes, tx_hash, status, gas_used, error))
        if status != 1:
            all_ok = False
            reason = f"step reverted (status 0): {step.description}"
            break
    end = _balances(w3, attacker_addresses)
    profit = end - start
    feasible = all_ok and profit > 0
    if all_ok and profit <= 0:
        reason = f"all steps succeeded but attacker did not profit ({profit} wei)"
    return SimResult(feasible, reason, profit, start, end, results)
