"""In-memory, org-scoped store of code repositories (a repo = named set of files + README + tree).
Like ScanStore, there is no cross-org accessor."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class RepoStore:
    _by_org: dict[str, dict[str, dict]] = field(default_factory=dict)

    def add(self, org_id: str, repo: dict) -> dict:
        stored = {"id": uuid.uuid4().hex, "org_id": org_id, **repo}
        self._by_org.setdefault(org_id, {})[stored["id"]] = stored
        return stored

    def list(self, org_id: str) -> list[dict]:
        return list(self._by_org.get(org_id, {}).values())

    def get(self, org_id: str, repo_id: str) -> dict | None:
        return self._by_org.get(org_id, {}).get(repo_id)

    def add_file(self, org_id: str, repo_id: str, path: str, content: str) -> dict | None:
        repo = self.get(org_id, repo_id)
        if repo is None:
            return None
        repo["files"][path] = content
        if path.endswith(".sol") and path not in repo["sol_paths"]:
            repo["sol_paths"] = sorted(repo["sol_paths"] + [path])
        # GitHub renders the repository-root README.md; keep the stored readme in sync.
        if path == "README.md":
            repo["readme"] = content
        return repo
