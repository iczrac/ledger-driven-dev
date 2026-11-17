#!/usr/bin/env bash
# 统一质量门禁：本地 / CI / 发布前跑同一份脚本，口径一致。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
MODE="${1:-all}"
DEMO="examples/demo-shop/governance"
FAILURES=0

note(){ printf '\n== %s ==\n' "$1"; }
pass(){ printf '[PASS] %s\n' "$1"; }
fail(){ printf '[FAIL] %s — %s\n' "$1" "$2"; FAILURES=$((FAILURES+1)); }

stage_tests(){
  note '单元测试（标准库 unittest）'
  python3 -m unittest discover -s tests -v
}
stage_evidence(){
  note '证据分层：生成实测报告并确认 verified 判定'
  local tmp report
  tmp="$(mktemp -d)"
  report="$tmp/report.json"
  python3 scripts/run_tests.py --dir examples/demo-shop/tests \
    --top examples/demo-shop --out "$report" --label gate || { rm -rf "$tmp"; return 1; }
  python3 - "$report" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
assert r['schema'] == 'ledger-test-report/1', '报告 schema 错误'
assert r['overall'] == 'pass', '测试未全过，不得升级 verified'
assert r['summary']['passed'] >= 3, '通过用例数异常'
assert r['evidence_binding']['inputs'], '报告未绑定源码摘要'
print(f"  实测报告 {r['summary']['passed']}/{r['summary']['total']} passed，overall={r['overall']}，"
      f"源码摘要 {r['evidence_binding']['source_digest']}")
PY
  local rc=$?
  rm -rf "$tmp"
  return $rc
}
stage_verify(){
  note '账本不变量（21 条）'
  python3 "$DEMO/verify_ledger.py" --root . \
    --registry "$DEMO/registry.json" \
    --ledger "$DEMO/DECISION_LEDGER.json" \
    --board "$DEMO/index.html" --strict
}
snapshot(){
  python3 - "$1" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(len(d['history']['events']),
      d['history']['events'][-1]['fingerprint_after'],
      sorted(c['id'] for c in d['lessons']['candidates']),
      [t['code'] for t in d['capability_model']['next_queue']])
PY
}
stage_idempotence(){
  note '生成器幂等（连续重跑，状态不变则不追加事件）'
  local tmp before after
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/examples/demo-shop/governance"
  cp -r examples/demo-shop/src examples/demo-shop/tests examples/demo-shop/docs "$tmp/examples/demo-shop/"
  cp "$DEMO"/* "$tmp/examples/demo-shop/governance/"
  local ledger="$tmp/examples/demo-shop/governance/DECISION_LEDGER.json"
  local board="$tmp/examples/demo-shop/governance/index.html"
  local reg="$tmp/examples/demo-shop/governance/registry.json"
  local report="$tmp/examples/demo-shop/governance/test_report.json"
  before="$(snapshot "$ledger")"
  # 示例账本处于 verified 稳态，重跑必须带同一份报告才幂等（证据消失则回落是预期语义）
  python3 "$DEMO/build_capability_model.py" --root "$tmp" --registry "$reg" \
    --ledger "$ledger" --board "$board" --test-report "$report" --strict-evidence >/dev/null 2>&1 || { rm -rf "$tmp"; return 1; }
  python3 "$DEMO/build_capability_model.py" --root "$tmp" --registry "$reg" \
    --ledger "$ledger" --board "$board" --test-report "$report" --strict-evidence >/dev/null 2>&1 || { rm -rf "$tmp"; return 1; }
  after="$(snapshot "$ledger")"
  rm -rf "$tmp"
  if [ "$before" != "$after" ]; then
    printf '  before: %s\n  after : %s\n' "$before" "$after"
    return 1
  fi
}
stage_sync(){
  note '模板 / 示例同步 + 看板 EMBED 一致'
  cmp -s templates/build_capability_model.py "$DEMO/build_capability_model.py" || return 1
  cmp -s templates/verify_ledger.py "$DEMO/verify_ledger.py" || return 1
  python3 - "$DEMO" <<'PY'
import json, re, sys
base = sys.argv[1]
html = open(f'{base}/index.html').read()
embed = json.loads(re.search(r'const EMBED = (\{.*?\});\nlet DATA', html, re.S).group(1))
ledger = json.load(open(f'{base}/DECISION_LEDGER.json'))
assert embed == ledger, '看板 EMBED 与账本不一致'
print('  看板 EMBED 与账本一致；模板脚本与示例副本一致')
PY
}
stage_scenarios(){
  note '场景矩阵 + 生命周期预检'
  python3 scripts/scenario_matrix.py --check || return 1
  python3 scripts/scenario_matrix.py --emit-md docs/generated/SCENARIO_MATRIX.md || return 1
  git diff --exit-code -- docs/generated/SCENARIO_MATRIX.md >/dev/null || return 1
  python3 scripts/scenario_guard.py --target examples/demo-shop --strict >/dev/null || return 1
  local tmp rc
  tmp="$(mktemp -d)"
  cp -r examples/demo-shop "$tmp/proj" || { rm -rf "$tmp"; return 1; }
  python3 scripts/lifecycle.py --target "$tmp/proj" freeze --reason "门禁自检" >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  python3 scripts/scenario_guard.py --target "$tmp/proj" --strict >/dev/null
  rc=$?
  rm -rf "$tmp"
  [ "$rc" -eq 2 ] || return 1
  echo '  场景定义自检、矩阵同步、预检放行与冻结拦截均通过'
}
stage_layout(){
  note '文件布局清单 + 只读 diff'
  python3 scripts/file_layout.py --check || return 1
  local tmp
  tmp="$(mktemp -d)"
  python3 scripts/file_layout.py --emit-md "$tmp/FILE_LAYOUT.md" >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  cmp -s "$tmp/FILE_LAYOUT.md" docs/generated/FILE_LAYOUT.md \
    || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  python3 scripts/file_layout.py --diff --target examples/demo-shop --strict >/dev/null || return 1
  cmp -s scripts/run_tests.py "$DEMO/run_tests.py" || return 1
  echo '  布局定义、渲染同步、示例骨架与第 3 个工具副本均一致'
}
stage_hygiene(){
  note '脱敏 + 文档内链'
  if grep -rliE 'RacOS|APEX|Tushare|tdx-connector|ClickHouse|Minervini|Keychain' \
      --include='*.py' --include='*.json' --include='*.html' --include='*.md' \
      --exclude='check.sh' --exclude='RELEASE_CHECKLIST.md' . >/dev/null 2>&1; then
    echo '  发现来源项目内部名词残留'
    return 1
  fi
  python3 - <<'PY'
import os, re
bad = []
for root, dirs, files in os.walk('.'):
    if '.git' in root:
        continue
    for f in files:
        if not f.endswith('.md'):
            continue
        p = os.path.join(root, f)
        for link in re.findall(r'\]\(([^)]+)\)', open(p).read()):
            if link.startswith(('http://', 'https://', '#')):
                continue
            target = os.path.normpath(os.path.join(root, link.split('#')[0]))
            if not os.path.exists(target):
                bad.append(f'{p} -> {link}')
if bad:
    raise SystemExit('  失效文档链接: ' + '; '.join(bad[:5]))
print('  脱敏无残留；文档内链全部有效')
PY
}

run(){ name="$1"; shift; if "$@"; then pass "$name"; else fail "$name" '见上方输出'; fi; }

if [ "$MODE" = "--only-idempotence" ]; then
  run '幂等' stage_idempotence
elif [ "$MODE" = "--help" ]; then
  echo "用法: bash scripts/check.sh [all|--only-idempotence|--help]"
else
  run '测试' stage_tests
  run '证据分层' stage_evidence
  run '账本校验' stage_verify
  run '场景矩阵' stage_scenarios
  run '文件布局' stage_layout
  run '幂等' stage_idempotence
  run '同步' stage_sync
  run '卫生' stage_hygiene
fi

printf '\n'
if [ "$FAILURES" -gt 0 ]; then
  printf '质量门禁失败：%d 个阶段未通过\n' "$FAILURES"
  exit 1
fi
printf '质量门禁全绿：测试 / 证据分层 / 21 条不变量 / 场景矩阵 / 文件布局 / 幂等 / 同步 / 脱敏 / 文档链接\n'
