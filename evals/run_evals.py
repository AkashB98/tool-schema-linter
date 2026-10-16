#!/usr/bin/env python3
"""Golden evals for tool-schema-linter.

Runs a pinned fixture corpus (good schemas, bad schemas, false-positive
traps) and asserts EXACT expected findings per fixture -- rule id, severity,
and JSON path must all match. Writes evals/eval_report.json (no timestamps,
fully deterministic: byte-identical across runs).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linter import lint_tool  # noqa: E402


def _here(*parts: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), *parts)


def _key(f):
    return (f.rule_id, f.severity, f.path)


def main() -> int:
    with open(_here("golden_cases.json"), encoding="utf-8") as fh:
        cases = json.load(fh)["cases"]

    results = []
    n_pass = 0
    for case in cases:
        findings = lint_tool(case["tool"])
        actual = [{"rule_id": f.rule_id, "severity": f.severity, "path": f.path}
                  for f in findings]
        expected = sorted(case["expected"],
                          key=lambda d: (d["rule_id"], d["severity"], d["path"]))
        actual_sorted = sorted(actual,
                               key=lambda d: (d["rule_id"], d["severity"], d["path"]))
        passed = actual_sorted == expected
        n_pass += passed
        results.append({
            "name": case["name"],
            "kind": case["kind"],
            "passed": passed,
            "expected_count": len(expected),
            "actual_count": len(actual_sorted),
            "findings": actual_sorted,
            "mismatch": None if passed else {
                "missing": [e for e in expected if e not in actual_sorted],
                "extra": [a for a in actual_sorted if a not in expected],
            },
        })
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {case['name']}: "
              f"{len(actual_sorted)} findings (expected {len(expected)})")

    report = {
        "tool": "tool-schema-linter",
        "cases": results,
        "summary": {
            "total": len(cases),
            "passed": n_pass,
            "failed": len(cases) - n_pass,
        },
        "notes": "Pinned golden corpus: good schemas must lint clean, bad "
                 "schemas must produce the exact pinned findings, FP traps "
                 "must not fire. Deterministic: findings sorted by "
                 "(rule_id, path, message); no timestamps in this report.",
    }
    with open(_here("eval_report.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")

    with open(_here("eval_report.json"), "rb") as fh:
        md5 = hashlib.md5(fh.read()).hexdigest()
    print(f"\neval_report.json md5: {md5}")
    print(f"{n_pass}/{len(cases)} golden evals passed")
    return 0 if n_pass == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())
