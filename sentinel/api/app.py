"""The secure API: JWT-verified HTTP + WebSocket, RBAC, and org-scoped tenancy on every route.

POST /scans runs a real static scan (compile + Slither + attack graph + grounded narrative) via an
injectable `scanner` (the real one by default; tests inject a fast stub to exercise auth alone).
Read routes expose the stored scan and its sub-resources (findings, graph, narratives), always scoped
to the caller's org.
"""

from __future__ import annotations

import os
from typing import Callable

from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from sentinel.api.auth import TokenError, create_access_token, role_at_least, verify_password, verify_token
from sentinel.api.repos import RepoStore
from sentinel.api.scanner import scan_files, scan_source_text
from sentinel.api.store import ScanStore, User

ACCESS_TTL = 3600


class LoginBody(BaseModel):
    username: str
    password: str


class ScanBody(BaseModel):
    name: str
    source: str


class DiffBody(BaseModel):
    baseline_scan_id: str
    name: str
    source: str
    threshold: float | None = None


class SimulateBody(BaseModel):
    scenario: str
    patched: bool = False
    eth_price_usd: str | None = None


class RepoBody(BaseModel):
    name: str
    github_url: str | None = None


class RepoFileBody(BaseModel):
    path: str
    content: str


class AnalyzeBody(BaseModel):
    path: str


def _summary(record: dict) -> dict:
    return {"id": record["id"], "name": record.get("name"), "compiler": record.get("compiler"),
            "contracts": record.get("contracts"), "findings": len(record.get("findings", [])),
            "max_severity": record.get("max_severity")}


def create_app(secret: str, users: dict[str, User], store: ScanStore | None = None,
               scanner: Callable[[str, str], dict] | None = None,
               cors_origins: list[str] | None = None) -> FastAPI:
    if not secret:
        raise RuntimeError("SENTINEL_JWT_SECRET is required; refusing to start with an empty secret")
    app = FastAPI(title="Sentinel API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins if cors_origins is not None else ["http://localhost:5173"],
        allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
    )
    store = store or ScanStore()
    repos = RepoStore()
    scanner = scanner or scan_source_text
    bearer = HTTPBearer(auto_error=False)  # we raise 401 ourselves, uniformly

    def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
        if creds is None:
            raise HTTPException(status_code=401, detail="missing bearer token")
        try:
            return verify_token(secret, creds.credentials)
        except TokenError as e:
            raise HTTPException(status_code=401, detail=str(e))

    def require(role: str):
        def dep(user: dict = Depends(current_user)) -> dict:
            if not role_at_least(user["role"], role):
                raise HTTPException(status_code=403, detail=f"requires role >= {role}")
            return user
        return dep

    def _owned(scan_id: str, user: dict) -> dict:
        record = store.get(user["org_id"], scan_id)  # scoped to the caller's org only
        if record is None:
            raise HTTPException(status_code=404, detail="scan not found")
        return record

    @app.post("/auth/login")
    def login(body: LoginBody):
        user = users.get(body.username)
        if user is None or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")
        token = create_access_token(secret, user.username, user.org_id, user.role, ACCESS_TTL)
        return {"access_token": token, "org_id": user.org_id, "role": user.role}

    @app.get("/me")
    def me(user: dict = Depends(current_user)):
        return {"sub": user["sub"], "org_id": user["org_id"], "role": user["role"]}

    @app.get("/scans")
    def list_scans(user: dict = Depends(current_user)):
        return {"org_id": user["org_id"], "scans": [_summary(r) for r in store.list(user["org_id"])]}

    @app.post("/scans", status_code=201)
    def create_scan(body: ScanBody, user: dict = Depends(require("analyst"))):
        record = scanner(body.name, body.source)
        return store.add(user["org_id"], record)

    @app.get("/scans/{scan_id}")
    def get_scan(scan_id: str, user: dict = Depends(current_user)):
        return _owned(scan_id, user)

    @app.get("/scans/{scan_id}/findings")
    def get_findings(scan_id: str, user: dict = Depends(current_user)):
        return {"findings": _owned(scan_id, user).get("findings", [])}

    @app.get("/scans/{scan_id}/graph")
    def get_graph(scan_id: str, user: dict = Depends(current_user)):
        return _owned(scan_id, user).get("graph", {"nodes": [], "edges": []})

    @app.get("/scans/{scan_id}/narratives")
    def get_narratives(scan_id: str, user: dict = Depends(current_user)):
        return {"narratives": _owned(scan_id, user).get("narratives", [])}

    # ---- repositories (GitHub-style) ----
    def _owned_repo(repo_id: str, user: dict) -> dict:
        repo = repos.get(user["org_id"], repo_id)
        if repo is None:
            raise HTTPException(status_code=404, detail="repository not found")
        return repo

    def _repo_summary(r: dict) -> dict:
        return {"id": r["id"], "name": r["name"], "source_kind": r["source_kind"],
                "files": len(r["files"]), "sol_files": len(r["sol_paths"]), "has_readme": bool(r.get("readme"))}

    @app.get("/repos")
    def list_repos(user: dict = Depends(current_user)):
        return {"repos": [_repo_summary(r) for r in repos.list(user["org_id"])]}

    @app.post("/repos", status_code=201)
    def create_repo(body: RepoBody, user: dict = Depends(require("analyst"))):
        if body.github_url:
            from sentinel.api.github_import import ImportError_, import_github
            try:
                imported = import_github(body.github_url)
            except ImportError_ as e:
                raise HTTPException(status_code=422, detail=str(e))
            repo = {"name": body.name, "source_kind": "github", "github_url": body.github_url,
                    "files": imported["files"], "readme": imported["readme"], "sol_paths": imported["sol_paths"]}
        else:
            repo = {"name": body.name, "source_kind": "upload", "files": {}, "readme": None, "sol_paths": []}
        return _repo_summary(repos.add(user["org_id"], repo))

    @app.get("/repos/{repo_id}")
    def get_repo(repo_id: str, user: dict = Depends(current_user)):
        r = _owned_repo(repo_id, user)
        return {"id": r["id"], "name": r["name"], "source_kind": r["source_kind"],
                "github_url": r.get("github_url"), "readme": r.get("readme"),
                "tree": sorted(r["files"].keys()), "sol_paths": r["sol_paths"]}

    @app.get("/repos/{repo_id}/file")
    def get_repo_file(repo_id: str, path: str, user: dict = Depends(current_user)):
        r = _owned_repo(repo_id, user)
        if path not in r["files"]:
            raise HTTPException(status_code=404, detail="file not found in repository")
        return {"path": path, "content": r["files"][path]}

    @app.post("/repos/{repo_id}/files", status_code=201)
    def add_repo_file(repo_id: str, body: RepoFileBody, user: dict = Depends(require("analyst"))):
        _owned_repo(repo_id, user)
        repos.add_file(user["org_id"], repo_id, body.path, body.content)
        return {"ok": True}

    @app.post("/repos/{repo_id}/analyze", status_code=201)
    def analyze_repo(repo_id: str, body: AnalyzeBody, user: dict = Depends(require("analyst"))):
        r = _owned_repo(repo_id, user)
        if body.path not in r["files"]:
            raise HTTPException(status_code=404, detail="file not found in repository")
        record = scan_files(r["files"], body.path, f"{r['name']}:{body.path}")
        record["repo_id"] = repo_id
        return store.add(user["org_id"], record)

    @app.get("/scans/{scan_id}/score")
    def get_score(scan_id: str, user: dict = Depends(current_user)):
        record = _owned(scan_id, user)
        # A static scan has no simulation, so a numeric risk score is not established. Report that
        # honestly (never a fabricated number); expose the Slither-sourced static severity separately.
        return {"score": {"status": "insufficient_data",
                          "reason": "feasibility requires simulation (POST /simulate); static scan only"},
                "static_max_severity": record.get("max_severity"),
                "severity_config": record.get("severity_config")}

    @app.post("/diff")
    def diff(body: DiffBody, user: dict = Depends(require("analyst"))):
        from sentinel.cli.gate import evaluate
        from sentinel.cli.scan import Finding
        from sentinel.cli.main import _load_severity
        baseline = _owned(body.baseline_scan_id, user)
        base_findings = [Finding(**f) for f in baseline.get("findings", [])]
        current = [Finding(**f) for f in scanner(body.name, body.source).get("findings", [])]
        threshold = body.threshold if body.threshold is not None else _load_severity()[1]
        return vars(evaluate(base_findings, current, threshold))

    @app.post("/simulate")
    def simulate(body: SimulateBody, user: dict = Depends(require("analyst"))):
        from sentinel.api.chain_ops import SCENARIOS, UnknownScenario, run_simulation
        try:
            return run_simulation(body.scenario, body.patched, body.eth_price_usd)
        except UnknownScenario:
            raise HTTPException(status_code=422, detail=(
                f"no deployment harness for scenario '{body.scenario}'. Real simulation is available "
                f"only for built-in reconstructions {sorted(SCENARIOS)}; arbitrary uploaded source "
                "cannot be auto-deployed/auto-exploited."))

    @app.post("/monitor/demo")
    def monitor_demo(user: dict = Depends(require("analyst"))):
        from sentinel.api.chain_ops import run_monitor_demo
        return run_monitor_demo()

    @app.websocket("/ws/scans")
    async def ws_scans(websocket: WebSocket, token: str | None = None):
        if token is None:
            await websocket.close(code=1008)  # policy violation
            return
        try:
            user = verify_token(secret, token)
        except TokenError:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        scans = store.list(user["org_id"])
        await websocket.send_json({"type": "snapshot", "org_id": user["org_id"],
                                   "scan_ids": [s["id"] for s in scans]})
        await websocket.close()

    app.state.store = store
    return app


def app_from_env() -> FastAPI:
    secret = os.environ.get("SENTINEL_JWT_SECRET", "")
    return create_app(secret, users={})
