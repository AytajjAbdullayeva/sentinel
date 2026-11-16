"""Repository endpoints: create, add file, browse, analyze — org-scoped. GitHub-URL validation."""

import pytest
from fastapi.testclient import TestClient

from sentinel.api.app import create_app
from sentinel.api.auth import create_access_token, hash_password
from sentinel.api.store import ScanStore, User

SECRET = "repo-api-secret-32-chars-minimum-abcdefgh"
VULN = ("pragma solidity 0.8.20;\ncontract Vault {\n mapping(address=>uint256) b;\n"
        " function deposit() external payable { b[msg.sender]+=msg.value; }\n"
        " function withdraw() external { uint256 x=b[msg.sender]; require(x>0);"
        " (bool ok,)=msg.sender.call{value:x}(\"\"); require(ok); b[msg.sender]=0; }\n}\n")


@pytest.fixture
def client():
    users = {"a": User("a", hash_password("pw"), "org-A", "analyst")}
    return TestClient(create_app(SECRET, users, ScanStore()))


def _auth(role="analyst", org="org-A"):
    return {"Authorization": f"Bearer {create_access_token(SECRET, 'u', org, role, 3600)}"}


def test_invalid_github_url_is_422(client):
    r = client.post("/repos", headers=_auth(), json={"name": "x", "github_url": "http://evil.example/x"})
    assert r.status_code == 422


def test_create_add_browse(client):
    rid = client.post("/repos", headers=_auth(), json={"name": "Demo"}).json()["id"]
    client.post(f"/repos/{rid}/files", headers=_auth(), json={"path": "src/Vault.sol", "content": VULN})
    repo = client.get(f"/repos/{rid}", headers=_auth()).json()
    assert repo["tree"] == ["src/Vault.sol"] and repo["sol_paths"] == ["src/Vault.sol"]
    f = client.get(f"/repos/{rid}/file", headers=_auth(), params={"path": "src/Vault.sol"}).json()
    assert "withdraw" in f["content"]


def test_repos_are_org_scoped(client):
    rid = client.post("/repos", headers=_auth(org="org-A"), json={"name": "Demo"}).json()["id"]
    assert client.get(f"/repos/{rid}", headers=_auth(org="org-B")).status_code == 404
    assert client.get("/repos", headers=_auth(org="org-B")).json()["repos"] == []


def test_viewer_cannot_create_repo(client):
    assert client.post("/repos", headers=_auth(role="viewer"), json={"name": "x"}).status_code == 403


@pytest.mark.fixtures
def test_analyze_repo_file_produces_findings(client):
    rid = client.post("/repos", headers=_auth(), json={"name": "Demo"}).json()["id"]
    client.post(f"/repos/{rid}/files", headers=_auth(), json={"path": "Vault.sol", "content": VULN})
    scan = client.post(f"/repos/{rid}/analyze", headers=_auth(), json={"path": "Vault.sol"}).json()
    assert scan["repo_id"] == rid and scan["max_severity"] >= 80
    assert any("withdraw" in f["entry"] for f in scan["findings"])


def test_root_readme_is_rendered(client):
    """Adding a repository-root README.md surfaces it on GET /repos/{id} (GitHub renders it)."""
    rid = client.post("/repos", headers=_auth(), json={"name": "Demo"}).json()["id"]
    assert client.get(f"/repos/{rid}", headers=_auth()).json()["readme"] is None
    client.post(f"/repos/{rid}/files", headers=_auth(), json={"path": "README.md", "content": "# Demo\nHello"})
    repo = client.get(f"/repos/{rid}", headers=_auth()).json()
    assert repo["readme"] == "# Demo\nHello"
    assert repo["tree"] == ["README.md"]
