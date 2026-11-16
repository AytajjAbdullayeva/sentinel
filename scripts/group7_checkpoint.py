"""Group 7 checkpoint: the same negative checks FAIL on an insecure baseline and PASS on the real app.

This makes 'written as failing tests first, then fixed until passing' concrete: the checks have teeth
(they catch the old codebase's exact bugs) and the secure implementation satisfies them.
"""

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from sentinel.api.app import create_app
from sentinel.api.auth import create_access_token, hash_password
from sentinel.api.store import ScanStore, User

_spec = importlib.util.spec_from_file_location(
    "insecure_baseline", Path(__file__).resolve().parent.parent / "tests" / "insecure_baseline.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
create_insecure_app = _mod.create_insecure_app

SECRET = "checkpoint-secret-32-chars-minimum-abcdef"
def _STUB(name, source):  # fast scanner stub: this checkpoint tests auth controls, not scanning
    return {"name": name, "findings": [], "graph": {"nodes": [], "edges": []},
            "narratives": [], "max_severity": 0.0}


def tok(**o):
    kw = dict(secret=SECRET, sub="x", org_id="org-A", role="analyst", ttl_seconds=3600)
    kw.update(o)
    return create_access_token(**kw)


def checks(client, secure: bool):
    h = lambda t: {"Authorization": f"Bearer {t}"}
    results = {}

    # 1. no token must be rejected
    results["no-token -> 401"] = client.get("/scans", headers={} if secure else {"X-Org-Id": "org-A"}).status_code == 401

    # seed a scan in org-A
    if secure:
        sid = client.post("/scans", headers=h(tok(org_id="org-A", role="analyst")),
                          json={"name": "s", "source": "contract S {}"}).json().get("id")
    else:
        sid = client.post("/scans", headers={"X-Org-Id": "org-A"}, json={"target": "org-A-secret"}).json().get("id")

    # 2. cross-tenant read must be denied
    if secure:
        results["cross-tenant read -> denied"] = client.get(f"/scans/{sid}", headers=h(tok(org_id="org-B"))).status_code == 404
    else:
        results["cross-tenant read -> denied"] = "error" in client.get(f"/scans/{sid}").json()

    # 3. viewer must not create
    if secure:
        results["viewer create -> 403"] = client.post("/scans", headers=h(tok(role="viewer")),
                                                       json={"name": "t", "source": "contract T {}"}).status_code == 403
    else:
        results["viewer create -> 403"] = client.post("/scans", headers={"X-Role": "viewer", "X-Org-Id": "org-A"},
                                                       json={"target": "t"}).status_code == 403

    # 4. forged-signature token must be rejected
    forged = create_access_token("attacker-secret", "x", "org-A", "admin", 3600)
    results["forged token -> 401"] = client.get("/scans", headers=h(forged)).status_code == 401

    # 5. websocket without a token must be rejected
    try:
        with client.websocket_connect("/ws/scans") as ws:
            ws.receive_json()
        results["ws no-token -> rejected"] = False
    except WebSocketDisconnect:
        results["ws no-token -> rejected"] = True
    return results


def main() -> None:
    users = {"adam": User("adam", hash_password("pw"), "org-A", "viewer")}
    insecure = TestClient(create_insecure_app(ScanStore()))
    secure = TestClient(create_app(SECRET, users, ScanStore(), scanner=_STUB))
    ins, sec = checks(insecure, secure=False), checks(secure, secure=True)

    print(f"{'security control':<32} {'INSECURE baseline':<20} {'SECURE app':<12}")
    print("-" * 66)
    for name in ins:
        ib = "PASS" if ins[name] else "FAIL (vulnerable)"
        sb = "PASS" if sec[name] else "FAIL"
        print(f"{name:<32} {ib:<20} {sb:<12}")
    print("-" * 66)
    print(f"insecure baseline: {sum(ins.values())}/{len(ins)} controls hold  (expected: few — it is the old bug)")
    print(f"secure app:        {sum(sec.values())}/{len(sec)} controls hold  (expected: all)")
    assert all(sec.values()), "secure app failed a control"
    assert not all(ins.values()), "insecure baseline unexpectedly passed everything"


if __name__ == "__main__":
    main()
