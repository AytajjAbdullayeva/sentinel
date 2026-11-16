"""The fact record. Every fact names its origin; nothing here carries an invented number."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field

# Slither's own label vocabularies, stored verbatim.
SLITHER_IMPACTS = {"High", "Medium", "Low", "Informational", "Optimization"}
SLITHER_CONFIDENCES = {"High", "Medium", "Low"}


@dataclass
class Location:
    file: str
    lines: list[int]


@dataclass
class Fact:
    kind: str  # "detector" (a Slither detector finding) | "structure" (read from Slither's IR)
    name: str  # detector id, e.g. "reentrancy-eth"; or structure kind, e.g. "external_call"
    file: str
    lines: list[int]
    contract: str | None
    function: str | None
    description: str
    origin: str  # "slither <version>" or "slither-ir <version>"
    # Verbatim Slither labels for detector facts; None for IR structure facts (Slither assigns none).
    slither_impact: str | None = None
    slither_confidence: str | None = None
    detail: dict = field(default_factory=dict)
    evidence: list[Location] = field(default_factory=list)

    @property
    def id(self) -> str:
        key = f"{self.kind}|{self.name}|{self.file}|{self.lines}|{self.contract}|{self.function}|{sorted(self.detail.items())}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def to_dict(self) -> dict:
        return asdict(self) | {"id": self.id}
