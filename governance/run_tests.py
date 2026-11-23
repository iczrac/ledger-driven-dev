#!/usr/bin/env python3
"""用标准库跑测试，产出机器可读证据报告（供生成器判定 verified 级证据）。

设计原则
--------
1. 零依赖：只用 unittest，报告是纯 JSON。
2. 证据可追溯：报告含每个用例的模块/类名、状态、耗时、运行时间戳。
3. 源码绑定：报告含测试文件的内容摘要，生成器据此判断证据是否对**当前**源码有效。

用法
----
    python3 scripts/run_tests.py --dir tests --out governance/test_report.json
    python3 scripts/run_tests.py --dir tests --out report.json --label unit

报告格式
--------
    {
      "schema": "ledger-test-report/1",
      "label": "unit",
      "generated_at": "YYYY-MM-DD HH:MM HKT",
      "test_dir": "tests",
      "command": "unittest discover -s tests",
      "summary": {"total": 30, "passed": 30, "failed": 0, "errors": 0, "skipped": 0},
      "cases": [
        {"id": "tests.test_x.TestY.test_z", "file": "tests/test_x.py",
         "status": "pass|fail|error|skip", "seconds": 0.001}
      ],
      "overall": "pass|fail",
      "evidence_binding": {
        "algorithm": "sha256-files-v1",
        "inputs": [{"path": "tests/test_x.py", "sha256": "..."}],
        "source_digest": "16位摘要"
      }
    }
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import time
import unittest
from datetime import datetime
from pathlib import Path


class _Recorder(unittest.TextTestResult):
    """在标准 runner 之上记录每个用例的结构化结果。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases: list[dict] = []
        self._start = 0.0

    def startTest(self, test):
        self._start = time.monotonic()
        super().startTest(test)

    def _case(self, test, status: str) -> dict:
        mod = getattr(test, "__class__", type(test))
        full = f"{mod.__module__}.{mod.__name__}.{test._testMethodName}"
        raw_file = self._test_filename(test)
        return {
            "id": full,
            "file": raw_file,
            "status": status,
            "seconds": round(time.monotonic() - self._start, 6),
        }

    @staticmethod
    def _test_filename(test) -> str:
        fn = getattr(test, "__file__", None)
        if fn:
            return str(fn)
        cls = type(test)
        mod = __import__(cls.__module__, fromlist=["__file__"])
        return str(getattr(mod, "__file__", ""))

    def addSuccess(self, test):
        self.cases.append(self._case(test, "pass"))
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.cases.append(self._case(test, "fail"))
        super().addFailure(test, err)

    def addError(self, test, err):
        self.cases.append(self._case(test, "error"))
        super().addError(test, err)

    def addSkip(self, test, reason):
        self.cases.append(self._case(test, "skip"))
        super().addSkip(test, reason)


def run(test_dir: Path, pattern: str = "test_*.py", top_dir: Path | None = None,
        source_dirs: list[str] | None = None) -> dict:
    """发现并运行测试，返回结构化报告。

    top_dir 是 import 根（测试里 from src.xxx 时的 src 所在目录）；默认取测试目录
    的父目录。它会被加入 sys.path，保证测试能按项目内的绝对导入正常加载。
    """
    test_dir = test_dir.resolve()
    top_dir = (top_dir or test_dir.parent).resolve()
    # 保证 top_dir 在 sys.path：测试常用「from src.xxx import ...」这类项目根导入
    import importlib.util
    import sys
    # 注入 import 根与测试目录本身：前者支持「from src.xxx」，后者支持「from _base」
    for p in (top_dir, test_dir, test_dir.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    # 不用 discover：它对无 __init__.py 的目录/嵌套 tests/ 目录行为不一致。
    # 直接扫描文件 + importlib 加载，稳定且能捕获每个文件的导入错误。
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    load_errors: list[str] = []
    for path in sorted(test_dir.rglob(pattern)):
        mod_name = f"_lld_{path.stem}_{abs(hash(str(path))) & 0xffff}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            if spec is None or spec.loader is None:
                load_errors.append(f"{path}: no spec")
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
            suite.addTests(loader.loadTestsFromModule(module))
        except Exception as exc:  # 导入失败也计入报告，避免"0 用例假通过"
            load_errors.append(f"{path}: {type(exc).__name__}: {exc}")

    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0, resultclass=_Recorder)
    result = runner.run(suite)

    cases = result.cases  # type: ignore[attr-defined]
    counts = {"pass": 0, "fail": 0, "error": 0, "skip": 0}
    for c in cases:
        counts[c["status"]] = counts.get(c["status"], 0) + 1

    # 归一文件路径为仓库/项目根相对（若可判断）
    try:
        cwd = Path.cwd().resolve()
        for c in cases:
            if c["file"]:
                try:
                    c["file"] = str(Path(c["file"]).resolve().relative_to(cwd))
                except ValueError:
                    pass
    except Exception:
        pass

    overall = "pass" if (
        counts["fail"] == 0 and counts["error"] == 0 and not load_errors
        and counts["pass"] > 0
    ) else "fail"
    # test_dir 归一为相对 cwd，避免机器绝对路径泄露到分发的账本/报告
    try:
        test_dir_display = str(test_dir.relative_to(Path.cwd().resolve()))
    except ValueError:
        test_dir_display = test_dir.name
    # 源码绑定摘要：把「这次通过」绑定到具体文件内容，而不是文件名或时间戳。
    # 生成器会在重跑时逐个重算；任一变化即判 stale，verified 自动回落 declared。
    # v2.20.0（B 项）：source_dirs 显式给出时一并绑定被测源码，口径对齐
    # work_panel import-report --source-dir；缺省仍只绑定测试，保持旧报告兼容。
    root = (top_dir or test_dir.parent).resolve()
    scan_bases = [test_dir]
    for rel in source_dirs or []:
        base = root / rel
        if not base.is_dir():
            raise ValueError(f"源码绑定目录不存在：{rel}")
        scan_bases.append(base)
    digest_inputs: list[dict] = []
    seen_paths: set[str] = set()
    for base in scan_bases:
        for path in sorted(base.rglob(pattern if base == test_dir else "*")):
            if not path.is_file():
                continue
            if base != test_dir and path.suffix not in {
                    ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java",
                    ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".scala", ".sql"}:
                continue
            try:
                rel = path.resolve().relative_to(Path.cwd().resolve()).as_posix()
            except ValueError:
                rel = path.name
            if rel in seen_paths:
                continue
            seen_paths.add(rel)
            digest_inputs.append({"path": rel,
                                  "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    binding = {
        "algorithm": "sha256-files-v1",
        "inputs": digest_inputs,
        "source_digest": hashlib.sha256(
            "".join(f"{i['path']}:{i['sha256']}\n" for i in digest_inputs).encode()
        ).hexdigest()[:16],
    }
    return {
        "schema": "ledger-test-report/1",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M HKT"),
        "test_dir": test_dir_display,
        "command": f"unittest load from {test_dir.name}",
        "load_errors": load_errors,
        "summary": {
            "total": len(cases),
            "passed": counts["pass"],
            "failed": counts["fail"],
            "errors": counts["error"],
            "skipped": counts["skip"],
        },
        "cases": cases,
        "overall": overall,
        "raw_tail": stream.getvalue().strip().splitlines()[-5:],
        "evidence_binding": binding,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default="tests", help="测试目录（默认 tests）")
    ap.add_argument("--top", help="import 根（测试里 from src.xxx 时的 src 所在目录，默认测试目录的父目录）")
    ap.add_argument("--pattern", default="test_*.py", help="用例文件模式")
    ap.add_argument("--source-dir", dest="source_dirs", default=None,
                    help="逗号分隔的源码绑定目录（如 src,tests）；缺省只绑定测试文件")
    ap.add_argument("--out", required=True, help="报告输出 JSON 路径")
    ap.add_argument("--label", default="unit", help="报告标签（如 unit/integration）")
    args = ap.parse_args()

    source_dirs = ([d.strip() for d in args.source_dirs.split(",") if d.strip()]
                   if args.source_dirs else None)
    report = run(Path(args.dir), args.pattern,
                 top_dir=Path(args.top) if args.top else None,
                 source_dirs=source_dirs)
    report["label"] = args.label

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2))

    s = report["summary"]
    print(f"[{report['overall'].upper()}] {s['passed']}/{s['total']} passed "
          f"(fail={s['failed']} error={s['errors']} skip={s['skipped']})")
    print(f"报告：{out} · 源码摘要 {report['evidence_binding']['source_digest']}")


if __name__ == "__main__":
    main()
