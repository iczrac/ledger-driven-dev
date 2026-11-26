#!/usr/bin/env python3
"""T4 比對器：Python canonical 与前端 recomputeHealth 逐栏比对共享 fixture。

仅 CI 调用（本地 check.sh 保持零 node 依赖）。退出码 0=等价，1=漂移。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOL = 1e-9


def _run(cmd: list[str]) -> list[dict]:
    done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"{cmd[0]} 失败：{done.stderr or done.stdout}")
    return json.loads(done.stdout)


def _walk(path: str, a, b, errors: list[str]) -> None:
    if isinstance(a, (int, float)) and not isinstance(a, bool) \
            and isinstance(b, (int, float)) and not isinstance(b, bool):
        if abs(float(a) - float(b)) > TOL:
            errors.append(f"{path}: py={a} js={b}")
        return
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            errors.append(f"{path}: keys py={sorted(a)} js={sorted(b)}")
            return
        for key in a:
            _walk(f"{path}.{key}", a[key], b[key], errors)
        return
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            errors.append(f"{path}: len py={len(a)} js={len(b)}")
            return
        for i, (x, y) in enumerate(zip(a, b)):
            _walk(f"{path}[{i}]", x, y, errors)
        return
    if a != b:
        errors.append(f"{path}: py={a!r} js={b!r}")


def main() -> None:
    py = _run([sys.executable, "tests/tools/health_equivalence_py.py"])
    js = _run(["node", "tests/tools/health_equivalence.js", str(ROOT)])
    errors: list[str] = []
    if len(py) != len(js):
        errors.append(f"case 数量 py={len(py)} js={len(js)}")
    for a, b in zip(py, js):
        _walk(a["name"], a, b, errors)
    if errors:
        print("健康度 Python/JS 等价比对失败：", file=sys.stderr)
        for e in errors[:20]:
            print("  " + e, file=sys.stderr)
        raise SystemExit(1)
    print(f"健康度 Python/JS 等价比对通过：{len(py)} 组 fixture 逐栏一致")


if __name__ == "__main__":
    main()
