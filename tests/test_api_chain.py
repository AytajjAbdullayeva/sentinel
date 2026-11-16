"""API completion: /diff (static gate), /score (honest), /simulate + /monitor/demo (real Anvil)."""

import pytest
from fastapi.testclient import TestClient

from sentinel.api.app import create_app
from sentinel.api.auth import create_access_token, hash_password
from sentinel.api.store import ScanStore, User

pytestmark = [pytest.mark.fixtures, pytest.mark.chain]

SECRET = "chain-api-secret-32-chars-minimum-abcdefgh"
SAFE = "pragma solidity 0.8.20;\ncontract Vault {\n mapping(address=>uint256) b;\n function deposit() external payable { b[msg.sender]+=msg.value; }\n function withdraw() external { uint256 x=b[msg.sender]; require(x>0); b[msg.sender]=0; (bool ok,)=msg.sender.call{value:x}(\"\"); require(ok); }\n}\n"
VULN = "pragma solidity 0.8.20;\ncontract Vault {\n mapping(address=>uint256) b;\n function deposit() external payable { b[msg.sender]+=msg.value; }\n function withdraw() external { uint256 x=b[msg.sender]; require(x>0); (bool ok,)=msg.sender.call{value:x}(\"\"); require(ok); b[msg.sender]=0; }\n}\n"


@pytest.fixture
def client():
    users = {"a": User("a", hash_password("pw"), "org-A", "analyst")}
    return TestClient(create_app(SECRET, users, ScanStore()))


def _auth(role="analyst", org="org-A"):
    return {"Authorization": f"Bearer {create_access_token(SECRET, 'u', org, role, 3600)}"}


def test_score_is_honest_insufficient_for_static_scan(client):
    sid = client.post("/scans", headers=_auth(), json={"name": "V", "source": VULN}).json()["id"]
    body = client.get(f"/scans/{sid}/score", headers=_auth()).json()
    assert body["score"]["status"] == "insufficient_data"
    assert body["static_max_severity"] >= 80  # Slither still reports the High reentrancy statically


def test_diff_gate_passes_unchanged_fails_on_regression(client):
    base = client.post("/scans", headers=_auth(), json={"name": "Vault", "source": SAFE}).json()["id"]
    unchanged = client.post("/diff", headers=_auth(),
                            json={"baseline_scan_id": base, "name": "Vault", "source": SAFE}).json()
    assert unchanged["failed"] is False and unchanged["exit_code"] == 0
    regressed = client.post("/diff", headers=_auth(),
                            json={"baseline_scan_id": base, "name": "Vault", "source": VULN}).json()
    assert regressed["failed"] is True and regressed["exit_code"] == 1


def test_diff_requires_analyst(client):
    base = client.post("/scans", headers=_auth(), json={"name": "V", "source": SAFE}).json()["id"]
    r = client.post("/diff", headers=_auth(role="viewer"),
                    json={"baseline_scan_id": base, "name": "V", "source": VULN})
    assert r.status_code == 403


def test_simulate_reentrancy_real_receipts(client):
    r = client.post("/simulate", headers=_auth(),
                    json={"scenario": "reentrancy", "patched": False, "eth_price_usd": "2500"}).json()
    assert r["feasible"] is True and r["profit_eth"] > 30
    assert all(s["tx_hash"] for s in r["steps"])
    assert r["score"]["status"] == "scored"
    patched = client.post("/simulate", headers=_auth(),
                          json={"scenario": "reentrancy", "patched": True}).json()
    assert patched["feasible"] is False


def test_simulate_unknown_scenario_is_honest_422(client):
    r = client.post("/simulate", headers=_auth(), json={"scenario": "my_uploaded_contract"})
    assert r.status_code == 422 and "no deployment harness" in r.json()["detail"]


def test_monitor_demo_reports_real_drift(client):
    r = client.post("/monitor/demo", headers=_auth()).json()
    assert r["quiet_poll"] == []
    kinds = {d["kind"] for d in r["drift"]}
    assert "implementation_upgraded" in kinds and "role_granted" in kinds
    assert all(d["evidence"]["tx_hash"] for d in r["drift"])
