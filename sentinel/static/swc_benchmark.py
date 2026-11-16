"""Precision/recall of the Slither fact source against labelled SWC Registry test cases.

Ground truth is the SWC Registry's own `.yaml` label files (commit 3b6a6773, the last commit that
shipped test cases). The detector -> SWC table below is used ONLY for this evaluation; it follows
each Slither detector's documented weakness class and is not consulted by the analyzer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from sentinel.static.slither_analyzer import analyze

SWC_ROOT = (Path(__file__).resolve().parent.parent.parent / "fixtures" / "external" / "swc_cases"
            / "test_cases" / "solidity")

PAIRS = [
    "reentracy/simple_dao",
    "reentracy/modifier_reentrancy",
    "tx_origin/mycontract",
    "delegate_call_to_untrusted_callee/proxy",
    "weak_randomness/guess_the_random_number",
    "uninitialised_storage_pointer/crypto_roulette",
    "shadowing_inherited_state_variables/TokenSale",
    "integer_overflow_and_underflow/overflow_simple_add",
    "pragma_not_locked/floating_pragma",
    "write_to_arbitrary_storage_location/arbitrary_location_write_simple",
]

DETECTOR_TO_SWC = {
    "reentrancy-eth": "SWC-107", "reentrancy-no-eth": "SWC-107", "reentrancy-benign": "SWC-107",
    "reentrancy-events": "SWC-107", "reentrancy-unlimited-gas": "SWC-107",
    "tx-origin": "SWC-115",
    "controlled-delegatecall": "SWC-112", "delegatecall-loop": "SWC-112",
    "weak-prng": "SWC-120",
    "uninitialized-storage": "SWC-109",
    "shadowing-state": "SWC-119",
    "arbitrary-send-eth": "SWC-105",
    "suicidal": "SWC-106",
    "unchecked-lowlevel": "SWC-104", "unchecked-send": "SWC-104",
    "timestamp": "SWC-116",
    "controlled-array-length": "SWC-124",
    "solc-version": "SWC-102",
    "incorrect-equality": "SWC-132",
}


@dataclass
class CaseResult:
    case: str
    vulnerable: bool
    target_swc: str
    label_lines: list[int]
    predicted_swcs: set[str]
    target_hit_lines: list[list[int]]
    detector_hits: dict[str, str] = field(default_factory=dict)  # detector id -> Slither confidence

    @property
    def predicted_target(self) -> bool:
        return self.target_swc in self.predicted_swcs

    @property
    def line_match(self) -> bool:
        return any(set(lines) & set(self.label_lines) for lines in self.target_hit_lines)


def _label(case_dir: Path) -> tuple[str, int, list[int]]:
    data = yaml.safe_load((case_dir / f"{case_dir.name}.yaml").read_text())
    issue = data["issues"][0]
    lines = [n for loc in issue.get("locations", []) for ns in loc.get("line_numbers", {}).values() for n in ns]
    return issue["id"], issue["count"], lines


def run_case(rel: str) -> CaseResult:
    case_dir = SWC_ROOT / rel
    swc, count, label_lines = _label(case_dir)
    result = analyze(case_dir / f"{case_dir.name}.sol", root=case_dir)
    detectors = result.detectors()
    predicted = {DETECTOR_TO_SWC[f.name] for f in detectors if f.name in DETECTOR_TO_SWC}
    hit_lines = [f.lines for f in detectors if DETECTOR_TO_SWC.get(f.name) == swc]
    hits = {}
    for f in detectors:
        hits.setdefault(f.name, f.slither_confidence)
    return CaseResult(rel, count > 0, swc, label_lines, predicted, hit_lines, hits)


def run() -> list[CaseResult]:
    return [run_case(r) for p in PAIRS for r in (p, f"{p}_fixed")]


def metrics(results: list[CaseResult]) -> dict:
    tp = sum(r.vulnerable and r.predicted_target for r in results)
    fn = sum(r.vulnerable and not r.predicted_target for r in results)
    fp = sum(not r.vulnerable and r.predicted_target for r in results)
    tn = sum(not r.vulnerable and not r.predicted_target for r in results)
    line_tp = sum(r.vulnerable and r.line_match for r in results)
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "line_level_recall": line_tp / (tp + fn) if tp + fn else None,
    }
