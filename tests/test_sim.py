"""Group 5: feasibility comes only from real receipts + measured balances.

The same attacker is run against the vulnerable and the patched contract; the engine reports
feasible=True (with real profit) on the former and feasible=False (with a real status-0 receipt or
no profit) on the latter. The engine is also shown to report infeasible when steps succeed but the
attacker does not profit — proving feasibility is measured, not assumed.
"""

import pytest
from web3 import Web3

from sentinel.sim import engine, exploits

pytestmark = [pytest.mark.fixtures, pytest.mark.chain]


def test_reentrancy_feasible_on_vulnerable_infeasible_on_fixed(anvil):
    w3 = anvil.w3
    vuln = engine.run(w3, *_scenario(exploits.reentrancy(w3, patched=False)))
    assert vuln.feasible is True
    assert all(s.ok for s in vuln.steps)
    assert vuln.attacker_profit_wei > w3.to_wei(30, "ether")  # deposited 10, drained ~60

    fixed = engine.run(w3, *_scenario(exploits.reentrancy(w3, patched=True)))
    assert fixed.feasible is False
    assert fixed.steps[0].status == 0  # attack() reverts: re-entrant withdraw hits zeroed balance
    assert fixed.attacker_profit_wei <= 0


def test_oracle_feasible_on_vulnerable_infeasible_on_fixed(anvil):
    w3 = anvil.w3
    vuln = engine.run(w3, *_scenario(exploits.oracle_manipulation(w3, patched=False)))
    assert vuln.feasible is True
    assert all(s.ok for s in vuln.steps)
    assert vuln.attacker_profit_wei > w3.to_wei(15, "ether")  # borrow 18 vs 1 collateral

    fixed = engine.run(w3, *_scenario(exploits.oracle_manipulation(w3, patched=True)))
    assert fixed.feasible is False
    assert fixed.steps[-1].status == 0  # borrow reverts: undercollateralized at the guarded price
    assert fixed.attacker_profit_wei <= 0


def test_engine_reports_infeasible_when_no_profit(anvil):
    """A strategy whose steps all succeed but earns nothing must be infeasible (measured, not assumed)."""
    w3 = anvil.w3
    attacker = w3.eth.accounts[8]
    noop = engine.Step("send 0-value self tx (succeeds, earns nothing)",
                       lambda: w3.eth.send_transaction({"from": attacker, "to": attacker, "value": 0,
                                                        "gas": 21000}))
    result = engine.run(w3, [attacker], [noop])
    assert result.steps[0].status == 1  # the step really succeeded
    assert result.feasible is False and result.attacker_profit_wei < 0  # only gas was spent


def _scenario(s: exploits.Scenario):
    return s.attacker_addresses, s.steps
