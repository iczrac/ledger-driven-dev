#!/usr/bin/env python3
"""T4 Python 侧：用 canonical compute_health_dimensions() 投影共享 fixture。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "templates"))
from build_capability_model import compute_health_dimensions  # noqa: E402


def main() -> None:
    fixture = json.loads((ROOT / "tests/fixtures/health_equivalence.json").read_text())
    out = []
    for case in fixture["cases"]:
        health = compute_health_dimensions(case["model"], case["ledger"])
        out.append({
            "name": case["name"],
            "dimensions": health["dimensions"],
            "overall": health["overall"],
            "coverage": health["coverage"],
        })
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
