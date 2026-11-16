"""Import a public GitHub repository: shallow-clone it and collect its Solidity files + README.

Only https://github.com/<owner>/<repo> URLs are accepted (no arbitrary hosts, no shell interpolation
— the URL is passed to git as a single argv). Clone is shallow, size- and time-bounded."""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

GITHUB_RE = re.compile(r"^https://github\.com/[\w.-]+/[\w.-]+(?:\.git)?/?$")
MAX_FILES = 400
MAX_FILE_BYTES = 400_000


class ImportError_(ValueError):
    pass


def import_github(url: str, timeout: int = 60) -> dict:
    url = url.strip()
    if not GITHUB_RE.match(url):
        raise ImportError_("only https://github.com/<owner>/<repo> URLs are allowed")
    with tempfile.TemporaryDirectory() as d:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, d],
            capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            raise ImportError_(f"git clone failed: {proc.stderr.strip()[:200]}")
        root = Path(d)
        files: dict[str, str] = {}
        readme = None
        for p in sorted(root.rglob("*")):
            if ".git" in p.parts or not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if p.suffix == ".sol":
                if p.stat().st_size <= MAX_FILE_BYTES:
                    files[rel] = p.read_text(errors="replace")
            elif p.name.lower() == "readme.md" and readme is None:
                readme = p.read_text(errors="replace")[:20_000]
            if len(files) > MAX_FILES:
                break
        if not files:
            raise ImportError_("no Solidity (.sol) files found in that repository")
        return {"files": files, "readme": readme, "sol_paths": sorted(files)}
