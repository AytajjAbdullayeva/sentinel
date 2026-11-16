"""A DELIBERATELY INSECURE API that reproduces the old Sentinel's auth bugs.

It exists only so the negative tests can be shown to FAIL against it (proving they have teeth) and
PASS against the real app. It is never imported by `sentinel/`. Its flaws are exactly the ones the
audit found in the old codebase: no token verification, an anonymous fallback, and no org scoping.
"""

from __future__ import annotations

from fastapi import FastAPI, Header, WebSocket

from sentinel.api.store import ScanStore


def create_insecure_app(store: ScanStore) -> FastAPI:
    app = FastAPI()

    def anon_user(x_org_id: str | None = Header(default=None), x_role: str | None = Header(default=None)):
        # BUG: trusts client-supplied headers; anonymous fallback to a demo org (the old behaviour).
        return {"org_id": x_org_id or "demo-org", "role": x_role or "viewer"}

    @app.get("/scans")
    def list_scans(x_org_id: str | None = Header(default=None)):
        user = anon_user(x_org_id)
        return {"org_id": user["org_id"], "scans": store.list(user["org_id"])}

    @app.get("/scans/{scan_id}")
    def get_scan(scan_id: str):
        for org in store._by_org.values():  # BUG: no org scoping — searches everyone's data
            if scan_id in org:
                return org[scan_id]
        return {"error": "not found"}

    @app.post("/scans", status_code=201)
    def create_scan(payload: dict, x_org_id: str | None = Header(default=None)):
        # BUG: no role check — a viewer can write.
        return store.add(x_org_id or "demo-org", {"name": payload.get("name", "?"), "status": "stub"})

    @app.websocket("/ws/scans")
    async def ws_scans(websocket: WebSocket, token: str | None = None):
        await websocket.accept()  # BUG: accepts with no token verification
        await websocket.send_json({"type": "snapshot", "org_id": "demo-org", "scan_ids": []})
        await websocket.close()

    return app
