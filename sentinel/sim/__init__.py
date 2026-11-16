"""Group 5 — real simulation: execute attack paths as real transactions on a local Anvil EVM.

Feasibility is never decided by this code. It is read from the transaction receipts (status) and from
the attacker's balance measured on-chain before and after. A path is feasible only if every step's
receipt has status 1 AND the attacker's measured balance strictly increased.
"""
