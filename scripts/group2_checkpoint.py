"""Group 2 checkpoint: Slither facts vs. SWC Registry labels, 10 vulnerable/fixed pairs."""

import json
from pathlib import Path

from sentinel.static import swc_benchmark
from sentinel.static.slither_analyzer import SLITHER_VERSION

OUT = Path(__file__).resolve().parent.parent / "out"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    results = swc_benchmark.run()
    print(f"slither {SLITHER_VERSION}; ground truth: SWC Registry yaml labels\n")
    print(f"{'case':<72} {'label':<9} {'target':<8} {'predicted?':<10} {'line match':<10} mapped SWCs")
    for r in results:
        label = f"{r.target_swc}x{1 if r.vulnerable else 0}"
        line = ("yes" if r.line_match else "no") if r.vulnerable else "-"
        print(f"{r.case:<72} {label:<9} {r.target_swc:<8} {str(r.predicted_target):<10} {line:<10} "
              f"{sorted(r.predicted_swcs)}")
    m = swc_benchmark.metrics(results)
    print("\nfile-level, target SWC per pair:")
    print(f"  TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']}")
    print(f"  precision={m['precision']:.2f}  recall={m['recall']:.2f}  line-level recall={m['line_level_recall']:.2f}")
    print("\ndetector hits with Slither confidence, per case:")
    for r in results:
        print(f"  {r.case}: {r.detector_hits}")
    (OUT / "group2.json").write_text(json.dumps(
        {"metrics": m, "cases": [r.__dict__ | {"predicted_swcs": sorted(r.predicted_swcs)} for r in results]},
        indent=2, default=list))


if __name__ == "__main__":
    main()
