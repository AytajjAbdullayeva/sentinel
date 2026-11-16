"""Group 7+ API over the REAL static scanner: create a scan from Solidity source, then read its
findings / graph / narratives — all org-scoped. Needs solc + Slither (fixtures marker)."""

import pytest
from fastapi.testclient import TestClient

from sentinel.api.app import create_app
from sentinel.api.auth import create_access_token, hash_password
from sentinel.api.store import ScanStore, User

pytestmark = pytest.mark.fixtures

SECRET = "scan-api-secret-32-chars-minimum-abcdefgh"
REENTRANT = """// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;
contract Vault {
    mapping(address => uint256) public balances;
    function deposit() external payable { balances[msg.sender] += msg.value; }
    function withdraw() external {
        uint256 bal = balances[msg.sender];
        require(bal > 0);
        (bool ok, ) = msg.sender.call{value: bal}("");
        require(ok);
        balances[msg.sender] = 0;
    }
}
"""


@pytest.fixture
def client():
    users = {"alice": User("alice", hash_password("pw"), "org-A", "analyst")}
    return TestClient(create_app(SECRET, users, ScanStore()))  # real scanner (default)


def _auth(org="org-A", role="analyst"):
    return {"Authorization": f"Bearer {create_access_token(SECRET, 'u', org, role, 3600)}"}


def test_create_scan_runs_real_static_analysis(client):
    r = client.post("/scans", headers=_auth(), json={"name": "Vault", "source": REENTRANT})
    assert r.status_code == 201, r.text
    rec = r.json()
    assert rec["compiler"].startswith("0.8.")
    assert rec["max_severity"] >= 80  # Slither reports reentrancy-eth (High) -> mapped to 80
    assert any("withdraw" in f["entry"] for f in rec["findings"])


def test_read_findings_graph_narratives(client):
    sid = client.post("/scans", headers=_auth(), json={"name": "Vault", "source": REENTRANT}).json()["id"]

    findings = client.get(f"/scans/{sid}/findings", headers=_auth()).json()["findings"]
    assert findings and any(any("reentrancy" in e for e in f["evidence"]) for f in findings)

    graph = client.get(f"/scans/{sid}/graph", headers=_auth()).json()
    assert graph["nodes"] and graph["edges"]
    assert all("data" in n and n["data"]["id"] for n in graph["nodes"])  # cytoscape shape
    assert all("provenance" in e["data"] for e in graph["edges"])        # every edge cites provenance

    narratives = client.get(f"/scans/{sid}/narratives", headers=_auth()).json()["narratives"]
    assert narratives and narratives[0]["claims"]
    for c in narratives[0]["claims"]:
        assert c["evidence"]  # grounded


def test_scan_subresources_are_org_scoped(client):
    sid = client.post("/scans", headers=_auth(org="org-A"), json={"name": "V", "source": REENTRANT}).json()["id"]
    for suffix in ("", "/findings", "/graph", "/narratives"):
        assert client.get(f"/scans/{sid}{suffix}", headers=_auth(org="org-B")).status_code == 404


def test_list_returns_summaries_only(client):
    client.post("/scans", headers=_auth(), json={"name": "Vault", "source": REENTRANT})
    scans = client.get("/scans", headers=_auth()).json()["scans"]
    assert scans and set(scans[0]) == {"id", "name", "compiler", "contracts", "findings", "max_severity"}
