"""In-memory tenant-scoped store of scan results. Every read is keyed by org_id — there is no
cross-org accessor at all, so a resolver cannot forget to scope a query."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class User:
    username: str
    password_hash: str
    org_id: str
    role: str


@dataclass
class ScanStore:
    _by_org: dict[str, dict[str, dict]] = field(default_factory=dict)

    def add(self, org_id: str, record: dict) -> dict:
        stored = {"id": uuid.uuid4().hex, "org_id": org_id, **record}
        self._by_org.setdefault(org_id, {})[stored["id"]] = stored
        return stored

    def list(self, org_id: str) -> list[dict]:
        return list(self._by_org.get(org_id, {}).values())

    def get(self, org_id: str, scan_id: str) -> dict | None:
        return self._by_org.get(org_id, {}).get(scan_id)
