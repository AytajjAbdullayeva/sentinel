"""Slither as the fact source.

Two kinds of facts come out:
  * detector facts — one per Slither detector result, with Slither's detector id, impact and
    confidence labels copied verbatim and the source lines Slither reported;
  * structure facts — entry points, calls, value transfers, delegatecalls, selfdestructs and state
    writes read from Slither's IR, each tied to the source lines of the IR node.
No regex, and no confidence value is ever produced by this module.
"""

from __future__ import annotations

import inspect
import os
from dataclasses import dataclass, field
from importlib.metadata import version
from pathlib import Path

from slither.core.declarations import Function
from slither.detectors import all_detectors
from slither.detectors.abstract_detector import AbstractDetector
from slither.slither import Slither
from slither.slithir.operations import HighLevelCall, LibraryCall, LowLevelCall, Send, SolidityCall, Transfer

from sentinel.ingest import pragma
from sentinel.ingest.solc import _available_versions, _solc_binary
from sentinel.static.facts import Fact, Location

SLITHER_VERSION = version("slither-analyzer")
_DETECTORS = [d for _, d in inspect.getmembers(all_detectors, inspect.isclass) if issubclass(d, AbstractDetector)]
_SELFDESTRUCT = {"selfdestruct(address)", "suicide(address)"}


@dataclass
class AnalysisResult:
    target: str
    solc_version: str
    slither_version: str
    facts: list[Fact] = field(default_factory=list)

    def detectors(self) -> list[Fact]:
        return [f for f in self.facts if f.kind == "detector"]

    def structure(self) -> list[Fact]:
        return [f for f in self.facts if f.kind == "structure"]


def _rel(path_abs: str, root: Path) -> str:
    return os.path.relpath(path_abs, root)


def analyze(target: Path, root: Path | None = None, solc_version: str | None = None) -> AnalysisResult:
    target = Path(target).resolve()
    root = Path(root).resolve() if root else target.parent
    solc_version = solc_version or pragma.resolve([target.read_text()], _available_versions())
    sl = Slither(str(target), solc=str(_solc_binary(solc_version)), compile_force_framework="solc")
    for det in _DETECTORS:
        sl.register_detector(det)

    facts: dict[str, Fact] = {}
    target_rel = _rel(str(target), root)
    for group in sl.run_detectors():
        for r in group:
            fact = _detector_fact(r, root, target_rel)
            facts[fact.id] = fact
    for fact in _structure_facts(sl, root):
        facts[fact.id] = fact
    return AnalysisResult(_rel(str(target), root), solc_version, SLITHER_VERSION, list(facts.values()))


def _detector_fact(r: dict, root: Path, target_rel: str) -> Fact:
    elements = r.get("elements", [])
    evidence = [Location(_rel(e["source_mapping"]["filename_absolute"], root), e["source_mapping"]["lines"])
                for e in elements if e.get("source_mapping")]
    # Most specific location: a statement ("node") element if Slither gave one, else the first element.
    primary = next((e for e in elements if e.get("type") == "node"), elements[0] if elements else None)
    fn = next((e for e in elements if e.get("type") == "function"), None)
    contract = None
    for e in elements:
        parent = e.get("type_specific_fields", {}).get("parent", {})
        if e.get("type") == "contract":
            contract = e["name"]
            break
        if parent.get("type") == "contract":
            contract = parent["name"]
            break
        grand = parent.get("type_specific_fields", {}).get("parent", {})
        if grand.get("type") == "contract":
            contract = grand["name"]
            break
    loc = primary["source_mapping"] if primary else None
    return Fact(
        kind="detector", name=r["check"],
        # A result with no source element (e.g. solc-version) is about the compilation unit, not a
        # line: it is attached to the analysed file and labelled scope=compiler, never given a line.
        file=_rel(loc["filename_absolute"], root) if loc else target_rel,
        lines=loc["lines"] if loc else [],
        contract=contract, function=fn["name"] if fn else None,
        description=r["description"].strip(),
        origin=f"slither {SLITHER_VERSION}",
        slither_impact=r["impact"], slither_confidence=r["confidence"],
        detail={} if loc else {"scope": "compiler"},
        evidence=evidence,
    )


def _structure_facts(sl: Slither, root: Path):
    origin = f"slither-ir {SLITHER_VERSION}"
    for c in sl.contracts:
        if c.is_interface:
            continue
        for f in c.functions_and_modifiers_declared:
            file = _rel(f.source_mapping.filename.absolute, root)
            where = dict(contract=c.name, function=f.full_name, origin=origin)
            is_entry = isinstance(f, Function) and not f.is_constructor and (
                f.visibility in ("public", "external") or f.is_fallback or f.is_receive)
            if is_entry:
                yield Fact("structure", "entry_point", file, list(f.source_mapping.lines),
                           description=f"{c.name}.{f.full_name} is externally callable",
                           detail={"visibility": f.visibility, "payable": f.payable, "view": f.view, "pure": f.pure,
                                   "modifiers": [m.name for m in f.modifiers],
                                   "checks_msg_sender": f.is_protected()},
                           **where)
            for node in f.nodes:
                lines = list(node.source_mapping.lines)
                for ir in node.irs:
                    if isinstance(ir, LowLevelCall):
                        name = "delegatecall" if ir.function_name == "delegatecall" else "low_level_call"
                        yield Fact("structure", name, file, lines, description=str(node.expression),
                                   detail={"destination": str(ir.destination), "sends_value": ir.call_value is not None},
                                   **where)
                        if ir.call_value is not None:
                            yield Fact("structure", "eth_transfer", file, lines, description=str(node.expression),
                                       detail={"via": ir.function_name, "destination": str(ir.destination)}, **where)
                    elif isinstance(ir, HighLevelCall) and not isinstance(ir, LibraryCall):
                        yield Fact("structure", "external_call", file, lines, description=str(node.expression),
                                   detail={"destination": str(ir.destination), "function": str(ir.function_name),
                                           "sends_value": ir.call_value is not None}, **where)
                    elif isinstance(ir, (Transfer, Send)):
                        yield Fact("structure", "eth_transfer", file, lines, description=str(node.expression),
                                   detail={"via": type(ir).__name__.lower(), "destination": str(ir.destination)},
                                   **where)
                    elif isinstance(ir, SolidityCall) and ir.function.name in _SELFDESTRUCT:
                        yield Fact("structure", "selfdestruct", file, lines, description=str(node.expression),
                                   detail={}, **where)
                for var in node.state_variables_written:
                    yield Fact("structure", "state_write", file, lines, description=str(node.expression),
                               detail={"variable": var.name}, **where)
