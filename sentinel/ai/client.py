"""LLM client abstraction plus a real stub.

StubLLMClient makes no network call, is deterministic, and never raises — so the narrative pipeline
runs to completion with no API key (the old codebase instead 401'd and errored the whole run).
`get_client()` returns the stub when no key is set. A real provider client is intentionally NOT
shipped untested: if a key is present but no real client has been wired and validated, we raise a
clear error rather than silently faking a response.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class LLMClient(ABC):
    name: str

    @abstractmethod
    def complete(self, prompt: str) -> str:
        ...


class StubLLMClient(LLMClient):
    name = "stub"

    def complete(self, prompt: str) -> str:
        # Deterministic, offline formatting of the (already-grounded) prompt lines into prose.
        lines = [ln.strip() for ln in prompt.splitlines() if ln.strip()]
        body = " ".join(lines)
        return f"[stub-narrative | offline, no API key] {body}"


def get_client() -> LLMClient:
    key = os.environ.get("SENTINEL_LLM_API_KEY", "")
    if not key:
        return StubLLMClient()
    raise RuntimeError(
        "SENTINEL_LLM_API_KEY is set but no real provider client has been wired and tested. "
        "Provide the key to the maintainer to implement and validate the real client; refusing to "
        "fake a response.")
