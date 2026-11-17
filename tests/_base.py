"""测试公共夹具：全部在临时目录复制示例，绝不污染真实账本。"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "demo-shop"
GOV = DEMO / "governance"
GENERATOR = GOV / "build_capability_model.py"
VERIFIER = GOV / "verify_ledger.py"

for extra in (ROOT / "scripts", ROOT / "templates", GOV):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def load_ledger() -> dict:
    return json.loads((GOV / "DECISION_LEDGER.json").read_text())


@contextmanager
def demo_copy():
    """复制完整示例到临时目录，yield (tmp_root, ledger, registry, board)。"""
    with __import__("tempfile").TemporaryDirectory() as td:
        tmp = Path(td)
        dst = tmp / "examples" / "demo-shop"
        shutil.copytree(DEMO, dst, ignore=shutil.ignore_patterns("__pycache__"))
        gov = dst / "governance"
        yield tmp, gov / "DECISION_LEDGER.json", gov / "registry.json", gov / "index.html"


def run_generator(root: Path, ledger: Path, registry: Path, board: Path,
                  dry: bool = False) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(GENERATOR), "--root", str(root),
           "--registry", str(registry), "--ledger", str(ledger), "--board", str(board)]
    if dry:
        cmd.append("--dry-run")
    return subprocess.run(cmd, capture_output=True, text=True)


def run_verify(root: Path, ledger: Path, registry: Path,
               board: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VERIFIER), "--root", str(root),
         "--registry", str(registry), "--ledger", str(ledger),
         "--board", str(board), "--json"],
        capture_output=True, text=True,
    )


def state_signature(ledger_path: Path) -> tuple:
    d = json.loads(ledger_path.read_text())
    return (
        len(d["history"]["events"]),
        d["history"]["events"][-1]["fingerprint_after"],
        tuple(sorted(c["id"] for c in d["lessons"]["candidates"])),
        tuple(t["code"] for t in d["capability_model"]["next_queue"]),
    )
