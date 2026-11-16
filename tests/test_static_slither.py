"""Group 2: Slither is the fact source; facts carry verbatim origin data and change with input."""

import pytest

from sentinel.static.facts import SLITHER_CONFIDENCES, SLITHER_IMPACTS
from sentinel.static.slither_analyzer import analyze
from sentinel.static.swc_benchmark import SWC_ROOT

pytestmark = pytest.mark.fixtures


def _case(rel):
    d = SWC_ROOT / rel
    if not d.exists():
        pytest.skip("SWC cases missing: run scripts/fetch_fixtures.sh")
    return analyze(d / f"{d.name}.sol", root=d)


@pytest.fixture(scope="module")
def dao():
    return _case("reentracy/simple_dao")


@pytest.fixture(scope="module")
def dao_fixed():
    return _case("reentracy/simple_dao_fixed")


def test_reentrancy_fact_has_verbatim_origin(dao):
    hits = [f for f in dao.detectors() if f.name.startswith("reentrancy")]
    assert hits, "Slither should report reentrancy in SimpleDAO"
    f = hits[0]
    assert f.file == "simple_dao.sol"
    assert set(f.lines) & {17, 18}  # SWC label lines
    assert f.slither_confidence in SLITHER_CONFIDENCES and f.slither_impact in SLITHER_IMPACTS
    assert f.origin.startswith("slither ")


def test_fixed_version_drops_the_reentrancy_eth_fact(dao, dao_fixed):
    assert any(f.name == "reentrancy-eth" for f in dao.detectors())
    assert not any(f.name == "reentrancy-eth" for f in dao_fixed.detectors())


def test_no_invented_confidence_anywhere(dao, dao_fixed):
    for result in (dao, dao_fixed):
        for f in result.facts:
            if f.kind == "detector":
                assert f.slither_confidence in SLITHER_CONFIDENCES
                assert f.slither_impact in SLITHER_IMPACTS
            else:
                assert f.slither_confidence is None and f.slither_impact is None
            assert not isinstance(f.slither_confidence, float)


def test_every_fact_has_a_source_location(dao):
    for f in dao.facts:
        assert f.file, f"{f.name} lacks a file"
        assert f.lines or f.detail.get("scope") == "compiler", f"{f.name} lacks lines and is not compiler-scoped"


def test_structure_facts_reflect_the_code(dao):
    names = {(f.name, f.function) for f in dao.structure()}
    assert ("eth_transfer", "withdraw(uint256)") in names
    assert ("low_level_call", "withdraw(uint256)") in names
    assert ("state_write", "withdraw(uint256)") in names


def test_different_contracts_give_different_facts(dao):
    other = _case("tx_origin/mycontract")
    assert {f.id for f in dao.facts}.isdisjoint({f.id for f in other.facts})
    assert any(f.name == "tx-origin" for f in other.detectors())
    assert not any(f.name == "tx-origin" for f in dao.detectors())
