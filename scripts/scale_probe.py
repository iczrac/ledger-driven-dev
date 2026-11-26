#!/usr/bin/env python3
"""规模基准：在临时目录合成一个大项目，真实跑一次生成器并量出代价。

为什么需要
----------
`scale_budget.py` 只报静态预算，无法回答「生成器在这个规模下到底要多久」。
本脚本是**可复现取证工具**：不写仓库、不改示例，所有产物都在临时目录，
结束后清理。用同一份生成器、同一份模板，规模由参数控制。

它同时暴露一个结构性事实：治理层文件数是固定的（不随模块数增长），
增长的是账本/看板体积、历史事件里的全量状态快照，以及生成器耗时。

用法
----
    python3 scripts/scale_probe.py --mods 5 --caps 10 --files 100 --json
    python3 scripts/scale_probe.py --mods 50 --caps 20 --files 1500 --events 80 --json

输出 schema: scale-probe/1。默认档很小，可直接进门禁；大档供人工取证。
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from board_path import filename_for

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "scale-probe/1"
GEN = ROOT / "templates" / "build_capability_model.py"
ADV = ROOT / "templates" / "binding_advisory.py"
CODEC = ROOT / "templates" / "registry_codec.py"
TEMPLATE = ROOT / "templates" / "index.html.template"


def build_project(base: Path, mods: int, caps_per: int, files: int,
                  entries: int, events: int) -> dict:
    gov = base / "governance"
    gov.mkdir(parents=True, exist_ok=True)
    for d in ("src/domain", "src/bulk", "src/contracts", "tests/unit",
              "docs/test_records", "docs/bulk"):
        (base / d).mkdir(parents=True, exist_ok=True)
    (base / "src" / "domain" / "order.py").write_text("x = 1\n", encoding="utf-8")
    for i in range(files):
        sub = ("src/bulk", "docs/bulk", "tests/unit")[i % 3]
        name = f"f{i:05d}.md" if sub == "docs/bulk" else f"f{i:05d}.py"
        (base / sub / name).write_text("x = 1\n", encoding="utf-8")
    modules = []
    for m in range(mods):
        caps = [{"name": f"能力{m}-{c}", "domain": f"D{c % 9:02d}",
                 "impl": ["src/domain/order.py"], "hints": ["order"]}
                for c in range(caps_per)]
        modules.append({"code": f"M{m:03d}", "name": f"模块{m:03d}",
                        "src": ["src/domain/"], "caps": caps})
    reg = {"project": {"code": "BIG", "name": "合成大项目", "root": ".",
                       "contracts_dir": "src/contracts", "unit_test_dir": "tests/unit",
                       "test_record_dir": "docs/test_records", "docs_dir": "docs",
                       "governance_dir": "governance", "governance_gate": True},
           "modules": modules}
    (gov / "registry.json").write_text(json.dumps(reg, ensure_ascii=False), encoding="utf-8")

    ent = [{"id": f"D-{i:04d}", "date": "2026-01-01", "status": "decided",
            "title": f"决策{i}", "decision": "x", "category": "架构",
            "evidence": [], "confidence": "high"} for i in range(entries)]
    codes = [f"BIG.M{m:03d}.D{c % 9:02d}.{c + 1:02d}"
             for m in range(mods) for c in range(caps_per)]
    digest = {code: {"l": 1, "c": 0.2} for code in codes}
    evs = [{"seq": i + 1, "ts": "2026-01-01", "type": "change",
            "fingerprint_before": "old", "fingerprint_after": f"fp{i:04d}",
            "changes": {"level_transitions": [], "added": [], "removed": [],
                        "completion_delta": [], "evidence_changes": []},
            "state_digest": digest, "trigger": "derive", "note": "合成历史事件"}
           for i in range(events)]
    ledger = {"ledger_version": "1.0", "title": "合成", "purpose": "规模基准",
              "last_updated": "", "owner": "x", "workflow": [], "fields": {},
              "entries": ent, "module_map": {"modules": []},
              "architecture": {"projects": []},
              "history": {"spec": {}, "events": evs},
              "lessons": {"spec": {}, "items": [], "candidates": []}}
    (gov / "DECISION_LEDGER.json").write_text(
        json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    tpl = TEMPLATE.read_text(encoding="utf-8")
    import re
    embed_re = re.compile(r"const EMBED = \{.*?\};\nlet DATA", re.S)
    (gov / filename_for(gov)).write_text(
        embed_re.sub(lambda _m: "const EMBED = {};\nlet DATA", tpl, count=1),
        encoding="utf-8")
    shutil.copyfile(GEN, gov / "build_capability_model.py")
    shutil.copyfile(ADV, gov / "binding_advisory.py")
    shutil.copyfile(ROOT / "templates" / "derived_issues.py", gov / "derived_issues.py")
    shutil.copyfile(CODEC, gov / "registry_codec.py")
    shutil.copyfile(ROOT / "templates" / "board_path.py", gov / "board_path.py")
    return {"mods": mods, "caps_per": caps_per, "caps": mods * caps_per,
            "files": files, "entries": entries, "events": events}


def probe(config: dict) -> dict:
    config = {**config, "caps": config["mods"] * config["caps_per"]}
    with tempfile.TemporaryDirectory(prefix="ledger-scale-") as td:
        base = Path(td)
        build_project(base, config["mods"], config["caps_per"], config["files"],
                      config["entries"], config["events"])
        gov = base / "governance"
        t0 = time.perf_counter()
        p = subprocess.run(
            [sys.executable, str(gov / "build_capability_model.py"),
             "--root", str(base), "--registry", str(gov / "registry.json"),
             "--ledger", str(gov / "DECISION_LEDGER.json"),
             "--board", str(gov / filename_for(gov))],
            capture_output=True, text=True, timeout=600)
        elapsed = time.perf_counter() - t0
        if p.returncode != 0:
            return {"schema": SCHEMA, "config": config, "ok": False,
                    "error": p.stderr[-600:] or p.stdout[-600:]}
        d = json.loads((gov / "DECISION_LEDGER.json").read_text(encoding="utf-8"))
        evs = d["history"]["events"]
        sys.path.insert(0, str(ROOT / "scripts"))
        from scale_budget import report  # noqa: E402
        budget = report(base)
        return {
            "schema": SCHEMA, "config": config, "ok": True,
            "elapsed_s": round(elapsed, 3),
            "products": {
                "ledger_bytes": (gov / "DECISION_LEDGER.json").stat().st_size,
                "board_bytes": (gov / filename_for(gov)).stat().st_size,
                "governance_files": len([x for x in gov.rglob("*") if x.is_file()]),
                "project_files": budget["metrics"]["project_files"],
            },
            "model": {"capabilities": d["capability_model"]["summary"]["capabilities"],
                      "events": len(evs),
                      "state_digest_codes": len(evs[-1].get("state_digest", {}))},
            "budget_status": budget["status"],
            "budget_alerts": [b["id"] for b in budget["budgets"] if b["status"] != "ok"],
        }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mods", type=int, default=5)
    ap.add_argument("--caps", type=int, default=10, dest="caps_per")
    ap.add_argument("--files", type=int, default=100)
    ap.add_argument("--entries", type=int, default=50)
    ap.add_argument("--events", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    config = {"mods": args.mods, "caps_per": args.caps_per, "files": args.files,
              "entries": args.entries, "events": args.events}
    r = probe(config)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        if not r["ok"]:
            print("规模基准失败：" + r["error"])
            return 1
        p, m = r["products"], r["model"]
        print(f"规模基准：{r['config']['caps']} 能力 / {r['config']['files']} 文件 / "
              f"{r['config']['entries']} 决策 / {r['config']['events']} 历史事件 → "
              f"{r['elapsed_s']}s；账本 {p['ledger_bytes']/1024:.1f} KiB · "
              f"看板 {p['board_bytes']/1024:.1f} KiB · 治理文件 {p['governance_files']} · "
              f"事件快照 {m['state_digest_codes']} 能力；预算 {r['budget_status']}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
