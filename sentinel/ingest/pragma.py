"""Resolve a compile unit's `pragma solidity` constraints to one concrete solc release.

Import resolution is plumbing, not fact extraction, so a regex over `pragma` lines is fine here.
"""

from __future__ import annotations

import re

Version = tuple[int, int, int]

_PRAGMA = re.compile(r"pragma\s+solidity\s+([^;]+);")
_TERM = re.compile(r"(\^|~|>=|<=|>|<|=)?\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def parse_version(text: str) -> Version:
    major, minor, patch = (int(p) for p in text.split("."))
    return major, minor, patch


def _caret_upper(v: Version) -> Version:
    if v[0] > 0:
        return (v[0] + 1, 0, 0)
    if v[1] > 0:
        return (0, v[1] + 1, 0)
    return (0, 0, v[2] + 1)


def _expr_to_groups(expr: str) -> list[list[tuple[str, Version]]]:
    """An OR-list of AND-groups of (operator, version) comparisons."""
    groups = []
    for alternative in expr.split("||"):
        constraints: list[tuple[str, Version]] = []
        for m in _TERM.finditer(alternative):
            op = m.group(1) or "="
            v = (int(m.group(2)), int(m.group(3) or 0), int(m.group(4) or 0))
            if op == "^":
                constraints += [(">=", v), ("<", _caret_upper(v))]
            elif op == "~":
                constraints += [(">=", v), ("<", (v[0], v[1] + 1, 0))]
            else:
                constraints.append((op, v))
        groups.append(constraints)
    return groups


def _holds(v: Version, op: str, bound: Version) -> bool:
    return {
        "=": v == bound,
        ">=": v >= bound,
        "<=": v <= bound,
        ">": v > bound,
        "<": v < bound,
    }[op]


def satisfies(v: Version, expr: str) -> bool:
    return any(all(_holds(v, op, b) for op, b in group) for group in _expr_to_groups(expr))


def pragmas_in(source: str) -> list[str]:
    return [m.group(1).strip() for m in _PRAGMA.finditer(source)]


def resolve(sources: list[str], available: list[str]) -> str:
    """Highest available release satisfying every pragma across the compile unit."""
    exprs = [e for s in sources for e in pragmas_in(s)]
    candidates = sorted((parse_version(a) for a in available), reverse=True)
    for v in candidates:
        if all(satisfies(v, e) for e in exprs):
            return ".".join(map(str, v))
    raise ValueError(f"no solc release satisfies all of: {exprs}")
