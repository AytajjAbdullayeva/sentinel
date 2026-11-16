"""Group 8: stable finding ids across runs, and a CI gate that passes on no-change and fails on a
newly introduced high-risk path. Also invokes the installed `sentinel` binary end to end."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sentinel.cli import gate, main, scan

pytestmark = pytest.mark.fixtures

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "fixtures" / "contracts" / "ci" / "baseline"
CHANGED = ROOT / "fixtures" / "contracts" / "ci" / "changed"
IMPACTS, THRESHOLD, _ = ({"High": 80, "Medium": 50, "Low": 20, "Informational": 5}, 60.0, "t")


def _scan(path):
    return scan.scan_source(scan.collect_sol(path), IMPACTS)


def test_stable_id_is_identical_across_runs_and_versions():
    a = {f.stable_id for f in _scan(BASELINE)}
    b = {f.stable_id for f in _scan(BASELINE)}
    assert a == b and a  # deterministic
    # same contract+signature in baseline and changed -> the withdraw path keeps its id
    changed_ids = {f.stable_id for f in _scan(CHANGED)}
    assert a & changed_ids, "the withdraw path id should be stable across the code change"


def test_gate_passes_on_no_change():
    base = _scan(BASELINE)
    result = gate.evaluate(base, _scan(BASELINE), THRESHOLD)
    assert result.failed is False and result.exit_code == 0


def test_gate_fails_when_reentrancy_introduced():
    base = _scan(BASELINE)
    result = gate.evaluate(base, _scan(CHANGED), THRESHOLD)
    assert result.failed is True and result.exit_code == 1
    assert result.added or result.raised
    hit = (result.added + result.raised)[0]
    assert "withdraw" in hit["entry"] and any("reentrancy" in e for e in hit["evidence"])


def test_baseline_is_below_threshold():
    for f in _scan(BASELINE):
        assert f.severity_score < THRESHOLD  # nothing high-risk in the safe baseline


def test_installed_binary_scan_and_gate(tmp_path):
    """Run the real `sentinel` console script, not the internal functions."""
    base_json = tmp_path / "base.json"
    scan_cmd = subprocess.run(["sentinel", "scan", str(BASELINE), "--out", str(base_json)],
                              capture_output=True, text=True)
    assert scan_cmd.returncode == 0, scan_cmd.stderr
    assert base_json.exists()

    # unchanged twice -> exit 0 both times
    for _ in range(2):
        r = subprocess.run(["sentinel", "diff", str(BASELINE), "--baseline", str(base_json)],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr

    # changed with the reentrancy bug -> non-zero
    r = subprocess.run(["sentinel", "diff", str(CHANGED), "--baseline", str(base_json)],
                       capture_output=True, text=True)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "FAIL" in r.stdout
