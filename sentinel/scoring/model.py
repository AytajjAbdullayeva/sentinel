"""Score inputs, components and results. Every component records its numeric value AND its origin."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Component:
    name: str
    value: float
    origin: str
    detail: dict = field(default_factory=dict)


@dataclass
class ScoreInput:
    """Real, pre-extracted inputs. None means 'not established' — never silently defaulted."""
    feasible: bool | None                  # Group 5 simulation
    feasibility_evidence: str | None       # "simulation" | "static" | None
    profit_wei: int | None                 # Group 5 measured attacker gain
    eth_price_usd: object | None           # Group 3 Quantity (declared or onchain), or None
    value_evidence: str | None             # "onchain" | "declared" | None
    source_is_public: bool                 # Group 4: attack path starts at ANYONE
    path_len_edges: int                    # Group 4: edges on the attack path
    reachable_assets: int                  # Group 4: asset sinks the attacker can reach
    total_assets: int                      # Group 4: asset sinks in the protocol
    depends_on_count: int                  # Group 4: external dependencies on the path
    controlling_authorities: int           # Group 4: authorities controlling the path
    target: str                            # human label for the scored path


@dataclass
class ScoreResult:
    status: str                            # "scored" | "infeasible" | "insufficient_data"
    score: float | None
    reason: str
    config_version: str
    target: str
    components: dict[str, Component] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)

    @property
    def display(self) -> str:
        if self.status == "insufficient_data":
            return f"insufficient data (missing: {', '.join(self.missing)})"
        if self.status == "infeasible":
            return "0.0 (simulation proved infeasible)"
        return f"{self.score:.2f}"

    def to_dict(self) -> dict:
        return {
            "status": self.status, "score": self.score, "reason": self.reason,
            "config_version": self.config_version, "target": self.target, "missing": self.missing,
            "components": {k: vars(c) for k, c in self.components.items()},
        }
