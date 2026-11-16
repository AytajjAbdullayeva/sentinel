"""Group 11 checkpoint: run the REAL test suite, generate the status report from its JUnit XML, print
it, and fail if it contains any marketing language or claims an unverified capability."""

import subprocess
import sys
from pathlib import Path

from sentinel.report.status import build_report, lint_marketing, parse_junit, render_markdown

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    xml = OUT / "junit.xml"
    print("running the real test suite to produce JUnit XML (this is the only source of truth) ...")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={xml}"],
        cwd=ROOT, capture_output=True, text=True)
    print(proc.stdout.splitlines()[-1] if proc.stdout else proc.stderr[-400:])

    report = build_report(parse_junit(xml))
    md = render_markdown(report, source=f"pytest --junitxml ({xml.name}), {report.total_passed} passed")
    (OUT / "STATUS.md").write_text(md)
    print("\n" + md)

    marketing = lint_marketing(md)
    print(f"\nmarketing-language lint: {marketing or 'clean'}")
    verified = [c for c in report.capabilities.values() if c.status == "VERIFIED"]
    print(f"VERIFIED capabilities: {len(verified)}; each backed by >=1 real passing test: "
          f"{all(c.passed for c in verified)}")
    assert not marketing, f"report contains marketing language: {marketing}"
    assert all(c.passed for c in verified), "a VERIFIED capability has no passing test"
    assert report.total_failed == 0, "there are failing tests; report would show FAILING"
    print(f"\nwrote {OUT / 'STATUS.md'}")


if __name__ == "__main__":
    main()
