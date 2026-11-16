"""The CI gate: diff current findings against a baseline by stable id. Exit non-zero on regressions."""

from __future__ import annotations

from dataclasses import dataclass, field

from sentinel.cli.scan import Finding


@dataclass
class GateResult:
    failed: bool
    threshold: float
    added: list[dict] = field(default_factory=list)     # new finding at/above threshold
    raised: list[dict] = field(default_factory=list)     # existing finding whose severity rose to/above threshold
    exit_code: int = 0


def evaluate(baseline: list[Finding], current: list[Finding], threshold: float) -> GateResult:
    base_by_id = {f.stable_id: f for f in baseline}
    added, raised = [], []
    for f in current:
        if f.severity_score < threshold:
            continue
        prev = base_by_id.get(f.stable_id)
        if prev is None:
            added.append({"stable_id": f.stable_id, "entry": f.entry, "impact": f.max_impact,
                          "severity": f.severity_score, "pattern": f.pattern, "evidence": f.evidence})
        elif f.severity_score > prev.severity_score:
            raised.append({"stable_id": f.stable_id, "entry": f.entry,
                           "from": prev.severity_score, "to": f.severity_score,
                           "impact": f.max_impact, "evidence": f.evidence})
    failed = bool(added or raised)
    return GateResult(failed=failed, threshold=threshold, added=added, raised=raised,
                      exit_code=1 if failed else 0)
