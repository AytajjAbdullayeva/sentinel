"""The scoring engine.

Score = F . C . L . (w_v.V + w_b.B + w_d.D + w_g.G) . K, all weights/references from the config.

Rules enforced here:
  * F (feasibility) must come from a real simulation (Group 5). If it was never simulated, the score
    is "insufficient_data". If simulation proved it infeasible, the result is "infeasible" (0), which
    is distinct from unknown.
  * V (value) needs a measured profit (Group 5) AND a real price (Group 3). If either is missing the
    whole score is "insufficient_data" — a value-at-risk term is never invented.
  * Every component carries its origin string. No scoring constant is a literal in this file.
"""

from __future__ import annotations

from decimal import Decimal

from sentinel.scoring.config import ScoringConfig
from sentinel.scoring.model import Component, ScoreInput, ScoreResult


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def score(inp: ScoreInput, cfg: ScoringConfig) -> ScoreResult:
    def insufficient(missing: list[str]) -> ScoreResult:
        return ScoreResult("insufficient_data", None,
                           f"cannot score without: {', '.join(missing)}", cfg.version, inp.target,
                           missing=missing)

    # F — feasibility, only from simulation.
    if inp.feasible is None or inp.feasibility_evidence is None:
        return insufficient(["feasibility (requires simulation, Group 5)"])
    if inp.feasibility_evidence != "simulation":
        return insufficient([f"simulation-grade feasibility (have '{inp.feasibility_evidence}')"])
    if inp.feasible is False:
        return ScoreResult("infeasible", 0.0, "simulation proved the path infeasible",
                           cfg.version, inp.target,
                           components={"F": Component("F", 0.0, "sim:feasible=False")})

    comps: dict[str, Component] = {"F": Component("F", 1.0, "sim:feasible=True")}

    # C — attacker capability required.
    c_val = cfg.capability_public if inp.source_is_public else cfg.capability_privileged
    comps["C"] = Component("C", c_val, f"graph:source={'public' if inp.source_is_public else 'privileged'}",
                           {"config": "capability_public" if inp.source_is_public else "capability_privileged"})

    # L — path length (shorter = easier), exponential decay from config.
    steps = max(inp.path_len_edges, 1)
    l_val = cfg.length_decay ** (steps - 1)
    comps["L"] = Component("L", l_val, f"graph:path_len_edges={inp.path_len_edges}",
                           {"decay": cfg.length_decay})

    # V — value at risk = measured profit x real price, normalized. Missing -> insufficient.
    if inp.profit_wei is None:
        return insufficient(["measured profit (Group 5 simulation)"])
    if inp.eth_price_usd is None or inp.value_evidence is None:
        return insufficient(["ETH price (onchain or declared, Group 3)"])
    profit_eth = Decimal(inp.profit_wei) / Decimal(10) ** 18
    value_usd = float(profit_eth * inp.eth_price_usd.amount)
    v_val = _clamp01(value_usd / cfg.value_reference_usd)
    comps["V"] = Component("V", v_val,
                           f"sim:profit={profit_eth:.4f}ETH x {inp.value_evidence}:price={inp.eth_price_usd.amount}",
                           {"value_usd": value_usd, "reference_usd": cfg.value_reference_usd})

    # B — blast radius = reachable / total asset sinks.
    b_val = _clamp01(inp.reachable_assets / inp.total_assets) if inp.total_assets else 0.0
    comps["B"] = Component("B", b_val, f"graph:reachable_assets={inp.reachable_assets}/{inp.total_assets}")

    # D — dependency sensitivity = external dependencies on path, normalized.
    d_val = _clamp01(inp.depends_on_count / cfg.dependency_reference)
    comps["D"] = Component("D", d_val, f"graph:depends_on={inp.depends_on_count}",
                           {"reference": cfg.dependency_reference})

    # G — governance/authority exposure on the path, normalized.
    g_val = _clamp01(inp.controlling_authorities / cfg.governance_reference)
    comps["G"] = Component("G", g_val, f"graph:controlling_authorities={inp.controlling_authorities}",
                           {"reference": cfg.governance_reference})

    # K — evidence confidence: feasibility grade x value grade.
    k_feas = cfg.k_sim_proven  # feasibility is simulation-grade here (checked above)
    k_value = cfg.k_value_onchain if inp.value_evidence == "onchain" else cfg.k_value_declared
    k_val = k_feas * k_value
    comps["K"] = Component("K", k_val, f"evidence:feasibility=simulation,value={inp.value_evidence}")

    value_term = (cfg.w_value * v_val + cfg.w_blast * b_val
                  + cfg.w_dependency * d_val + cfg.w_governance * g_val)
    raw = comps["F"].value * c_val * l_val * value_term * k_val
    final = raw * cfg.scale
    return ScoreResult("scored", final,
                       "F.C.L.(w_v.V+w_b.B+w_d.D+w_g.G).K over fully-sourced inputs",
                       cfg.version, inp.target, components=comps)
