"""Group 7 negative tests (written first): missing / malformed / expired / forged tokens, RBAC,
cross-tenant isolation, and WebSocket auth. All run against the real app and must pass."""

import base64
import json
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sentinel.api.app import create_app
from sentinel.api.auth import create_access_token, hash_password
from sentinel.api.store import ScanStore, User

SECRET = "test-secret-please-rotate-32chars-minimum-xx"
SCAN_BODY = {"name": "Demo", "source": "contract Demo {}"}


def _stub_scanner(name, source):  # fast, no solc/slither — these tests exercise auth, not scanning
    return {"name": name, "compiler": "0.8.0", "contracts": 1, "facts": 0, "max_severity": 0.0,
            "findings": [], "graph": {"nodes": [], "edges": []}, "narratives": []}


@pytest.fixture
def env():
    users = {
        "alice": User("alice", hash_password("pw-alice"), "org-A", "analyst"),
        "adam": User("adam", hash_password("pw-adam"), "org-A", "viewer"),
        "bob": User("bob", hash_password("pw-bob"), "org-B", "analyst"),
    }
    store = ScanStore()
    return TestClient(create_app(SECRET, users, store, scanner=_stub_scanner)), users, store


def _token(**over):
    kw = dict(secret=SECRET, sub="x", org_id="org-A", role="analyst", ttl_seconds=3600)
    kw.update(over)
    return create_access_token(**kw)


def _auth(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---- token verification (the old code verified nothing) -----------------------------------------

def test_missing_token_is_401(env):
    client, *_ = env
    assert client.get("/scans").status_code == 401


def test_malformed_token_is_401(env):
    client, *_ = env
    assert client.get("/scans", headers=_auth("not.a.jwt")).status_code == 401


def test_wrong_signature_is_401(env):
    client, *_ = env
    forged = create_access_token("attacker-secret", "x", "org-A", "admin", 3600)
    assert client.get("/scans", headers=_auth(forged)).status_code == 401


def test_alg_none_token_is_401(env):
    client, *_ = env
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    none_tok = f"{b({'alg': 'none', 'typ': 'JWT'})}.{b({'sub':'x','org_id':'org-A','role':'admin','exp':time.time()+99,'iat':time.time(),'type':'access'})}."
    assert client.get("/scans", headers=_auth(none_tok)).status_code == 401


def test_expired_token_is_401(env):
    client, *_ = env
    expired = _token(ttl_seconds=-10)
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(expired, SECRET, algorithms=["HS256"])  # confirm it really is expired
    assert client.get("/scans", headers=_auth(expired)).status_code == 401


def test_valid_token_allows_access(env):
    client, *_ = env
    assert client.get("/scans", headers=_auth(_token())).status_code == 200


# ---- login --------------------------------------------------------------------------------------

def test_login_wrong_password_is_401(env):
    client, *_ = env
    assert client.post("/auth/login", json={"username": "alice", "password": "nope"}).status_code == 401


def test_login_success_returns_scoped_token(env):
    client, *_ = env
    r = client.post("/auth/login", json={"username": "alice", "password": "pw-alice"})
    assert r.status_code == 200 and r.json()["org_id"] == "org-A" and r.json()["role"] == "analyst"


# ---- RBAC ---------------------------------------------------------------------------------------

def test_viewer_cannot_create_scan(env):
    client, *_ = env
    tok = _token(role="viewer")
    r = client.post("/scans", headers=_auth(tok), json=SCAN_BODY)
    assert r.status_code == 403


def test_analyst_can_create_scan(env):
    client, *_ = env
    r = client.post("/scans", headers=_auth(_token(role="analyst")),
                    json=SCAN_BODY)
    assert r.status_code == 201


# ---- multi-tenancy ------------------------------------------------------------------------------

def test_cross_tenant_read_is_404_and_list_is_isolated(env):
    client, users, store = env
    created = client.post("/scans", headers=_auth(_token(org_id="org-A", role="analyst")),
                          json={"name": "secret", "source": "contract S {}"}).json()
    sid = created["id"]
    # org-B cannot read org-A's scan by id ...
    assert client.get(f"/scans/{sid}", headers=_auth(_token(org_id="org-B"))).status_code == 404
    # ... and it does not appear in org-B's list, only in org-A's.
    assert sid not in [s["id"] for s in client.get("/scans", headers=_auth(_token(org_id="org-B"))).json()["scans"]]
    assert sid in [s["id"] for s in client.get("/scans", headers=_auth(_token(org_id="org-A"))).json()["scans"]]


# ---- websocket ----------------------------------------------------------------------------------

def test_ws_without_token_is_rejected(env):
    client, *_ = env
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/scans") as ws:
            ws.receive_json()


def test_ws_expired_token_is_rejected(env):
    client, *_ = env
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(f"/ws/scans?token={_token(ttl_seconds=-10)}") as ws:
            ws.receive_json()


def test_ws_valid_token_streams_only_own_org(env):
    client, users, store = env
    client.post("/scans", headers=_auth(_token(org_id="org-A", role="analyst")),
                json=SCAN_BODY)
    with client.websocket_connect(f"/ws/scans?token={_token(org_id='org-B')}") as ws:
        msg = ws.receive_json()
    assert msg["org_id"] == "org-B" and msg["scan_ids"] == []  # org-B sees none of org-A's scans
