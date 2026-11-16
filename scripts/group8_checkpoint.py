"""Group 8 checkpoint: drive the INSTALLED `sentinel` binary; show real exit codes.

Baseline scanned, then diffed twice unchanged (must be 0,0), then diffed against a version with a
deliberately introduced reentrancy bug (must be non-zero).
"""

import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "fixtures" / "contracts" / "ci" / "baseline"
CHANGED = ROOT / "fixtures" / "contracts" / "ci" / "changed"


def run(*args):
    r = subprocess.run(["sentinel", *args], capture_output=True, text=True)
    print(f"$ sentinel {' '.join(args)}\n{r.stdout}{r.stderr}exit={r.returncode}\n")
    return r.returncode


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        base_json = Path(d) / "base.json"
        codes = {}
        codes["scan_baseline"] = run("scan", str(BASE), "--out", str(base_json))
        codes["diff_unchanged_1"] = run("diff", str(BASE), "--baseline", str(base_json))
        codes["diff_unchanged_2"] = run("diff", str(BASE), "--baseline", str(base_json))
        codes["diff_changed"] = run("diff", str(CHANGED), "--baseline", str(base_json))
        print("exit codes:", codes)
        assert codes["diff_unchanged_1"] == 0 and codes["diff_unchanged_2"] == 0, "unchanged must pass"
        assert codes["diff_changed"] != 0, "introduced high-risk change must fail the gate"
        print("\nGATE BEHAVES CORRECTLY: unchanged -> 0,0 ; high-risk change -> non-zero")


if __name__ == "__main__":
    main()
