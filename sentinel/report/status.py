"""Build a capability status report from a real pytest JUnit XML file.

A capability is marked VERIFIED only when it has >=1 passing test and 0 failing/errored tests, and the
report lists the exact passing test node ids behind it. A capability with no tests is UNTESTED — never
'done'. The text is then linted against a marketing-word denylist so no line can read as a claim that
isn't a test result.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# Test module -> the capability it exercises. Anything unmapped is grouped under "Other".
CAPABILITIES = {
    "test_primitives": "Ingestion primitives (keccak selectors, EIP slots, pragma resolution)",
    "test_ingest_real": "Real ingestion (solc compile, selectors vs solc, proxy detection)",
    "test_static_slither": "Static analysis (Slither facts with verbatim origin)",
    "test_value_authority": "Value & authority (two-origin values, storage holdings, on-chain authority)",
    "test_graph_paths": "Attack graph paths (Yen k-shortest vs networkx)",
    "test_graph_build": "Attack graph build (exploit topologies, provenance)",
    "test_sim": "Simulation (feasibility from real Anvil receipts)",
    "test_scoring": "Scoring formula (sourced inputs, insufficient-data)",
    "test_scoring_pipeline": "Scoring end-to-end (ranking on real reconstructions)",
    "test_api_auth": "Auth & multi-tenancy (JWT, RBAC, cross-tenant isolation)",
    "test_cli_gate": "CLI + CI gate (stable ids, gate can fail)",
    "test_monitor": "Monitoring (drift only from real chain events)",
    "test_ai_narrative": "AI narrative (grounded claims, hallucination removed)",
    "test_report": "Reporting honesty (status from real results, marketing lint)",
}

MARKETING_DENYLIST = [
    "revolutionary", "world-class", "world class", "best-in-class", "best in class", "cutting-edge",
    "cutting edge", "seamless", "bulletproof", "unbreakable", "industry-leading", "industry leading",
    "state-of-the-art", "state of the art", "magic", "guarantee", "guaranteed", "flawless",
    "enterprise-grade", "next-generation", "game-changing", "unhackable", "military-grade",
]


@dataclass
class TestCase:
    module: str
    name: str
    status: str  # "passed" | "failed" | "skipped"

    @property
    def nodeid(self) -> str:
        return f"{self.module}::{self.name}"


@dataclass
class Capability:
    label: str
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.failed:
            return "FAILING"
        if self.passed:
            return "VERIFIED"
        if self.skipped:
            return "SKIPPED"
        return "UNTESTED"


@dataclass
class StatusReport:
    capabilities: dict[str, Capability]
    total_passed: int
    total_failed: int
    total_skipped: int


def parse_junit(xml_path: Path) -> list[TestCase]:
    root = ET.parse(xml_path).getroot()
    cases = []
    for tc in root.iter("testcase"):
        classname = tc.get("classname", "")
        module = classname.split(".")[-1] if classname else "unknown"
        status = "passed"
        if tc.find("failure") is not None or tc.find("error") is not None:
            status = "failed"
        elif tc.find("skipped") is not None:
            status = "skipped"
        cases.append(TestCase(module, tc.get("name", "?"), status))
    return cases


def build_report(cases: list[TestCase]) -> StatusReport:
    caps: dict[str, Capability] = {}
    for c in cases:
        label = CAPABILITIES.get(c.module, "Other")
        cap = caps.setdefault(label, Capability(label))
        getattr(cap, c.status).append(c.nodeid)
    return StatusReport(
        capabilities=caps,
        total_passed=sum(c.status == "passed" for c in cases),
        total_failed=sum(c.status == "failed" for c in cases),
        total_skipped=sum(c.status == "skipped" for c in cases),
    )


def render_markdown(report: StatusReport, source: str) -> str:
    lines = ["# Sentinel — Verified Capability Status",
             "",
             f"Generated from real test results: {source}",
             f"Totals: {report.total_passed} passed, {report.total_failed} failed, "
             f"{report.total_skipped} skipped.",
             "",
             "| Capability | Status | Passing tests |",
             "|---|---|---|"]
    for cap in sorted(report.capabilities.values(), key=lambda c: c.label):
        lines.append(f"| {cap.label} | {cap.status} | {len(cap.passed)} |")
    lines += ["", "## Evidence (passing test node ids)", ""]
    for cap in sorted(report.capabilities.values(), key=lambda c: c.label):
        if cap.passed:
            lines.append(f"### {cap.label} — {cap.status}")
            lines += [f"- `{nid}`" for nid in cap.passed]
            lines.append("")
    return "\n".join(lines)


def lint_marketing(text: str) -> list[str]:
    low = text.lower()
    return [w for w in MARKETING_DENYLIST if w in low]
