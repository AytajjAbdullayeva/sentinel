"""Group 11: the report is derived from real results, never claims an untested/failing capability, and
carries no marketing language."""

from sentinel.report.status import (build_report, lint_marketing, parse_junit, render_markdown)

JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest">
  <testcase classname="tests.test_sim" name="test_reentrancy_feasible"/>
  <testcase classname="tests.test_sim" name="test_oracle_feasible"/>
  <testcase classname="tests.test_scoring" name="test_weights_sum"><failure message="boom">x</failure></testcase>
  <testcase classname="tests.test_monitor" name="test_skipme"><skipped message="no anvil"/></testcase>
</testsuite></testsuites>
"""


def _report(tmp_path):
    xml = tmp_path / "junit.xml"
    xml.write_text(JUNIT)
    return build_report(parse_junit(xml))


def test_parsing_counts_statuses(tmp_path):
    r = _report(tmp_path)
    assert r.total_passed == 2 and r.total_failed == 1 and r.total_skipped == 1


def test_verified_only_when_passing_and_no_failures(tmp_path):
    r = _report(tmp_path)
    by_label = {c.label: c for c in r.capabilities.values()}
    sim = by_label["Simulation (feasibility from real Anvil receipts)"]
    assert sim.status == "VERIFIED" and len(sim.passed) == 2
    scoring = by_label["Scoring formula (sourced inputs, insufficient-data)"]
    assert scoring.status == "FAILING"  # a failing test must never read as verified
    monitor = by_label["Monitoring (drift only from real chain events)"]
    assert monitor.status == "SKIPPED"


def test_report_lists_real_nodeids_only(tmp_path):
    r = _report(tmp_path)
    md = render_markdown(r, source="junit.xml")
    assert "test_sim::test_reentrancy_feasible" in md
    assert "test_weights_sum" not in md.split("## Evidence")[1]  # failing test not listed as evidence


def test_generated_report_has_no_marketing_language(tmp_path):
    md = render_markdown(_report(tmp_path), source="junit.xml")
    assert lint_marketing(md) == []


def test_lint_catches_marketing():
    assert "revolutionary" in lint_marketing("Our revolutionary, bulletproof engine")
    assert "bulletproof" in lint_marketing("Our revolutionary, bulletproof engine")
