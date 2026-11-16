"""Group 6 pure scoring: deterministic formula, sourced inputs, insufficient-data on any missing input."""

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from sentinel.scoring import config as scfg
from sentinel.scoring.engine import score
from sentinel.scoring.model import ScoreInput
from sentinel.value.model import Declared, OnchainRead, Quantity

CFG = scfg.load()
PRICE_DECL = Quantity(Decimal(2500), "USD", Declared("t", "2026-09-24", "illustrative"))
PRICE_ONCHAIN = Quantity(Decimal(2500), "USD", OnchainRead(1, 100, "0x" + "22" * 20, "latestAnswer()", "2500"))


def _input(**over):
    base = dict(feasible=True, feasibility_evidence="simulation", profit_wei=50 * 10**18,
                eth_price_usd=PRICE_DECL, value_evidence="declared", source_is_public=True,
                path_len_edges=2, reachable_assets=1, total_assets=1, depends_on_count=0,
                controlling_authorities=0, target="test")
    base.update(over)
    return ScoreInput(**base)


def test_weights_must_sum_to_one(tmp_path):
    bad = tmp_path / "c.json"
    bad.write_text('{"version":"x","w_value":0.5,"w_blast":0.5,"w_dependency":0.5,"w_governance":0.5,'
                   '"capability_public":1,"capability_privileged":0.3,"length_decay":0.85,'
                   '"value_reference_usd":1,"dependency_reference":1,"governance_reference":1,'
                   '"k_sim_proven":1,"k_static_only":0.4,"k_value_onchain":1,"k_value_declared":0.7,"scale":100}')
    with pytest.raises(ValueError):
        scfg.load(bad)


def test_feasible_path_is_scored_with_sourced_components():
    r = score(_input(), CFG)
    assert r.status == "scored" and 0 < r.score < 100
    assert set(r.components) == {"F", "C", "L", "V", "B", "D", "G", "K"}
    for c in r.components.values():
        assert c.origin  # every component names where it came from
    assert r.components["V"].origin.startswith("sim:profit=")
    assert r.config_version == CFG.version


def test_infeasible_from_simulation_scores_zero_not_unknown():
    r = score(_input(feasible=False), CFG)
    assert r.status == "infeasible" and r.score == 0.0


def test_missing_feasibility_is_insufficient_data():
    r = score(_input(feasible=None, feasibility_evidence=None), CFG)
    assert r.status == "insufficient_data" and r.score is None and r.missing


def test_static_only_feasibility_is_insufficient():
    r = score(_input(feasibility_evidence="static"), CFG)
    assert r.status == "insufficient_data"


def test_missing_price_is_insufficient_no_invented_value():
    r = score(_input(eth_price_usd=None, value_evidence=None), CFG)
    assert r.status == "insufficient_data" and any("price" in m for m in r.missing)


def test_onchain_value_evidence_scores_higher_than_declared():
    declared = score(_input(value_evidence="declared", eth_price_usd=PRICE_DECL), CFG)
    onchain = score(_input(value_evidence="onchain", eth_price_usd=PRICE_ONCHAIN), CFG)
    assert onchain.score > declared.score  # K rewards stronger evidence


def test_reentrancy_outranks_oracle_and_scores_differ():
    reentrancy = score(_input(profit_wei=50 * 10**18, depends_on_count=0, target="reentrancy"), CFG)
    oracle = score(_input(profit_wei=17 * 10**18, depends_on_count=1, target="oracle"), CFG)
    assert reentrancy.score > oracle.score
    assert abs(reentrancy.score - oracle.score) > 1.0  # not a coincidental tie
    assert reentrancy.score == pytest.approx(26.80, abs=0.1)
    assert oracle.score == pytest.approx(20.93, abs=0.1)


def test_score_changes_when_input_changes():
    low = score(_input(profit_wei=1 * 10**18), CFG).score
    high = score(_input(profit_wei=100 * 10**18), CFG).score
    assert high > low


def test_no_numeric_fallbacks_in_scoring_code():
    """Constitution #1 extended to scoring: no `or <n>`, `.get(k,<n>)`, numeric param defaults."""
    root = Path(__file__).resolve().parent.parent

    def numeric(node):
        return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)

    offenders = []
    for path in (root / "sentinel" / "scoring").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.Or) and any(map(numeric, node.values)):
                offenders.append(f"{path.name}:{node.lineno} or <number>")
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get" and len(node.args) == 2 and numeric(node.args[1])):
                offenders.append(f"{path.name}:{node.lineno} .get(k,<number>)")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for d in node.args.defaults + node.args.kw_defaults:
                    if d is not None and numeric(d):
                        offenders.append(f"{path.name}:{node.lineno} numeric default in {node.name}()")
    assert not offenders, offenders
