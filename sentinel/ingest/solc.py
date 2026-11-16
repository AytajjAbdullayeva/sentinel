"""Real compilation through solc's standard-JSON interface.

Everything here comes from compiler output: ABI, creation/runtime bytecode, immutable
references, method identifiers and the AST. Nothing is inferred from source text except the
`pragma` line used to pick a compiler release.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from solc_select import solc_select

from sentinel.ingest import pragma
from sentinel.ingest.selectors import cross_check, selectors_from_abi, signature


@dataclass
class FunctionInfo:
    name: str
    signature: str
    selector: str
    state_mutability: str
    # Where the definition lives, from the AST `src` field. None when the ABI entry cannot be
    # tied to exactly one AST node (e.g. an ambiguous overload on a pre-0.6.2 compiler).
    source_file: str | None
    line: int | None


@dataclass
class ContractArtifact:
    name: str
    source_file: str
    kind: str  # "contract" | "interface" | "library"
    abstract: bool
    compiler_version: str
    abi: list[dict]
    bytecode: str  # creation code, hex without 0x
    deployed_bytecode: str  # runtime code, hex without 0x
    immutable_references: dict = field(default_factory=dict)
    functions: list[FunctionInfo] = field(default_factory=list)
    # solc `storageLayout` (slots/offsets/types of state variables); {} on compilers older than 0.5.13.
    storage_layout: dict = field(default_factory=dict)
    # Assets only exist for a deployed instance (see sentinel.value.holdings); a source artifact
    # never claims any, so this stays explicitly unknown rather than an empty list.
    assets: None = None
    assets_status: str = "not_analyzed"

    @property
    def deployable(self) -> bool:
        return self.kind == "contract" and not self.abstract and bool(self.bytecode)

    @property
    def fqn(self) -> str:
        return f"{self.source_file}:{self.name}"


@dataclass
class CompileResult:
    compiler_version: str
    settings: dict
    contracts: list[ContractArtifact]
    warnings: list[str]

    def get(self, name: str) -> ContractArtifact:
        hits = [c for c in self.contracts if c.name == name]
        if len(hits) != 1:
            raise KeyError(f"{name}: {len(hits)} matches")
        return hits[0]


class CompilationError(RuntimeError):
    pass


def _solc_binary(version: str) -> Path:
    if version not in solc_select.installed_versions():
        if not solc_select.install_artifacts([version]):
            raise CompilationError(f"could not install solc {version}")
    return Path(solc_select.artifact_path(version))


def _available_versions() -> list[str]:
    return list(solc_select.get_available_versions())


def compile_unit(entry_files: list[str], root: Path, optimizer_runs: int | None = 200,
                 version: str | None = None) -> CompileResult:
    """Compile `entry_files` (paths relative to `root`); solc resolves the imports itself."""
    root = Path(root).resolve()
    texts = [(root / f).read_text() for f in entry_files]
    version = version or pragma.resolve(texts, _available_versions())
    settings = {
        "optimizer": {"enabled": optimizer_runs is not None, "runs": optimizer_runs or 200},
        "outputSelection": {
            "*": {
                "*": ["abi", "evm.bytecode.object", "evm.deployedBytecode.object",
                      "evm.deployedBytecode.immutableReferences", "evm.methodIdentifiers",
                      "storageLayout"],
                "": ["ast"],
            }
        },
    }
    std_in = {"language": "Solidity",
              "sources": {f: {"urls": [f]} for f in entry_files},
              "settings": settings}
    proc = subprocess.run([str(_solc_binary(version)), "--standard-json", "--allow-paths", "."],
                          input=json.dumps(std_in), capture_output=True, text=True, cwd=root, check=False)
    if not proc.stdout:
        raise CompilationError(proc.stderr)
    out = json.loads(proc.stdout)
    errors = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errors:
        raise CompilationError("\n".join(e.get("formattedMessage", e["message"]) for e in errors))
    warnings = [e.get("formattedMessage", e["message"]) for e in out.get("errors", []) if e.get("severity") != "error"]
    contracts = _artifacts(out, root, version)
    return CompileResult(version, settings, contracts, warnings)


# ---- AST helpers -------------------------------------------------------------------------------

def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _line_of(src: str, file_bytes: dict[int, tuple[str, bytes]]) -> tuple[str | None, int | None]:
    start, _length, file_idx = (int(x) for x in src.split(":"))
    if file_idx not in file_bytes:
        return None, None
    path, data = file_bytes[file_idx]
    return path, data[:start].count(b"\n") + 1


def _artifacts(out: dict, root: Path, version: str) -> list[ContractArtifact]:
    file_bytes = {meta["id"]: (path, (root / path).read_bytes()) for path, meta in out["sources"].items()}
    contract_nodes: dict[int, dict] = {}
    contract_file: dict[int, str] = {}
    for path, meta in out["sources"].items():
        for node in _walk(meta["ast"]):
            if node.get("nodeType") == "ContractDefinition":
                contract_nodes[node["id"]] = node
                contract_file[node["id"]] = path

    result = []
    for path, by_name in out.get("contracts", {}).items():
        for name, c in by_name.items():
            node = next(n for i, n in contract_nodes.items() if n["name"] == name and contract_file[i] == path)
            ours = selectors_from_abi(c["abi"])
            cross_check(ours, c["evm"]["methodIdentifiers"], f"{path}:{name}")
            art = ContractArtifact(
                name=name,
                source_file=path,
                kind=node.get("contractKind", "contract"),
                abstract=bool(node.get("abstract", False)) or node.get("fullyImplemented") is False,
                compiler_version=version,
                abi=c["abi"],
                bytecode=c["evm"]["bytecode"]["object"],
                deployed_bytecode=c["evm"]["deployedBytecode"]["object"],
                immutable_references=c["evm"]["deployedBytecode"].get("immutableReferences", {}),
                storage_layout=c.get("storageLayout") or {},
            )
            art.functions = _functions(c["abi"], node, contract_nodes, file_bytes)
            result.append(art)
    return result


def _functions(abi, node, contract_nodes, file_bytes) -> list[FunctionInfo]:
    """Tie each ABI function to its AST definition along the inheritance chain."""
    bases = [contract_nodes[i] for i in node.get("linearizedBaseContracts", [node["id"]]) if i in contract_nodes]
    infos = []
    for entry in abi:
        if entry.get("type") != "function":
            continue
        sig = signature(entry)
        sel = selectors_from_abi([entry])[sig]
        loc = _locate(entry, sel, bases, file_bytes)
        infos.append(FunctionInfo(entry["name"], sig, sel, entry.get("stateMutability", ""), *loc))
    return infos


def _locate(entry, sel, bases, file_bytes):
    n_params = len(entry.get("inputs", []))
    for base in bases:  # most-derived first
        exact, by_name = [], []
        for sub in base.get("nodes", []):
            if sub.get("nodeType") == "FunctionDefinition" and sub.get("name") == entry["name"]:
                if sub.get("functionSelector") == sel:
                    exact.append(sub)
                elif "functionSelector" not in sub and len(sub["parameters"]["parameters"]) == n_params:
                    by_name.append(sub)
            elif (sub.get("nodeType") == "VariableDeclaration" and sub.get("name") == entry["name"]
                  and sub.get("visibility") == "public"):
                exact.append(sub)
        if exact:
            return _line_of(exact[0]["src"], file_bytes)
        if len(by_name) == 1:
            return _line_of(by_name[0]["src"], file_bytes)
        if len(by_name) > 1:
            return None, None  # ambiguous overload: say so rather than guess
    return None, None
