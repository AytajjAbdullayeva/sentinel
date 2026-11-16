"""`sentinel` CLI. Real subcommands via argparse (no single-command collapse).

    sentinel scan <path> [--json] [--out baseline.json]
    sentinel diff --baseline <baseline.json> <path> [--threshold N] [--json]

`diff` is the CI gate: it exits 1 when a finding at/above the threshold is newly introduced or its
severity rises versus the baseline, and 0 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sentinel.cli import gate, scan

SEVERITY_CONFIG = Path(__file__).resolve().parent.parent.parent / "fixtures" / "cli" / "severity.json"


def _load_severity() -> tuple[dict, float, str]:
    data = json.loads(SEVERITY_CONFIG.read_text())
    return data["impact_scores"], float(data["default_threshold"]), data["version"]


def _scan(path: Path):
    sol = scan.collect_sol(path)
    if not sol:
        print(f"error: no .sol files under {path}", file=sys.stderr)
        raise SystemExit(2)
    impacts, _default, version = _load_severity()
    return scan.scan_source(sol, impacts), version


def cmd_scan(args) -> int:
    findings, version = _scan(Path(args.path))
    if args.out:
        scan.write_baseline(Path(args.out), findings, version)
    if args.json:
        print(json.dumps({"version": version, "path": str(args.path),
                          "findings": [f.__dict__ for f in findings]}, indent=2))
    else:
        print(f"sentinel scan {args.path}  (severity config {version})")
        if not findings:
            print("  no attacker-reachable paths found")
        for f in findings:
            print(f"  [{f.max_impact:<13} {f.severity_score:5.1f}] {f.entry} -> {f.sink}"
                  f"  id={f.stable_id}  pattern={f.pattern or '-'}")
            for e in f.evidence:
                print(f"        {e}")
        if args.out:
            print(f"  wrote baseline: {args.out}")
    return 0


def cmd_diff(args) -> int:
    impacts, default_threshold, version = _load_severity()
    threshold = default_threshold if args.threshold is None else float(args.threshold)
    baseline = scan.read_baseline(Path(args.baseline))
    current, _ = _scan(Path(args.path))
    result = gate.evaluate(baseline, current, threshold)
    if args.json:
        print(json.dumps(result.__dict__, indent=2))
    else:
        print(f"sentinel diff  baseline={args.baseline}  target={args.path}  threshold={threshold}")
        for a in result.added:
            print(f"  NEW HIGH-RISK  {a['entry']}  {a['impact']} ({a['severity']})  id={a['stable_id']}")
            for e in a["evidence"]:
                print(f"        {e}")
        for r in result.raised:
            print(f"  SEVERITY ROSE  {r['entry']}  {r['from']} -> {r['to']} ({r['impact']})  id={r['stable_id']}")
            for e in r["evidence"]:
                print(f"        {e}")
        verdict = "FAIL (regression)" if result.failed else "PASS (no new high-risk paths)"
        print(f"  gate: {verdict}  exit={result.exit_code}")
    return result.exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sentinel", description="Attack-path intelligence for Solidity")
    sub = parser.add_subparsers(dest="command", required=True)

    ps = sub.add_parser("scan", help="scan a file or directory for attacker-reachable paths")
    ps.add_argument("path")
    ps.add_argument("--json", action="store_true")
    ps.add_argument("--out", help="write findings as a baseline JSON file")
    ps.set_defaults(func=cmd_scan)

    pd = sub.add_parser("diff", help="CI gate: compare a target against a baseline; exit 1 on regression")
    pd.add_argument("path")
    pd.add_argument("--baseline", required=True)
    pd.add_argument("--threshold", default=None, help="severity threshold (default from config)")
    pd.add_argument("--json", action="store_true")
    pd.set_defaults(func=cmd_diff)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
