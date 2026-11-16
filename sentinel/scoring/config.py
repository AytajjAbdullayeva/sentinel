"""Scoring configuration, loaded from a versioned JSON file. No scoring number is a code literal."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent.parent / "fixtures" / "scoring" / "config.json"


@dataclass(frozen=True)
class ScoringConfig:
    version: str
    w_value: float
    w_blast: float
    w_dependency: float
    w_governance: float
    capability_public: float
    capability_privileged: float
    length_decay: float
    value_reference_usd: float
    dependency_reference: float
    governance_reference: float
    k_sim_proven: float
    k_static_only: float
    k_value_onchain: float
    k_value_declared: float
    scale: float

    def __post_init__(self):
        total = self.w_value + self.w_blast + self.w_dependency + self.w_governance
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"value-term weights must sum to 1, got {total}")


def load(path: Path = DEFAULT_CONFIG) -> ScoringConfig:
    data = json.loads(Path(path).read_text())
    fields = ScoringConfig.__dataclass_fields__
    return ScoringConfig(**{k: v for k, v in data.items() if k in fields})
