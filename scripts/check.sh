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
  note '单元测试（unittest discover 与 run_tests.py 双口径，必须同数）'
  python3 -m unittest discover -s tests -v >/dev/null || return 1
  local tmp report
  tmp="$(mktemp -d)"
  report="$tmp/repo-tests.json"
  python3 scripts/run_tests.py --dir tests --top . --out "$report" --label repo >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  python3 - "$report" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))
assert r['schema'] == 'ledger-test-report/1', '报告 schema 错误'
assert r['overall'] == 'pass', '仓库自身测试未全过'
assert r['summary']['total'] >= 170, '用例数异常'
m = json.load(open('tests/MODULES.json'))
assert len(r['evidence_binding']['inputs']) == sum(len(x['files']) for x in m['modules']), \
    '测试架构清单与发现口径不一致'
print(f"  仓库测试 {r['summary']['passed']}/{r['summary']['total']} passed · "
      f"绑定 {len(r['evidence_binding']['inputs'])} 个模块内测试文件")
PY
  local rc=$?
  rm -rf "$tmp"
  return $rc
}
stage_test_modules(){
  note '测试架构：模块清单 / MODULE_ID / 发现口径 / 目标项目缺口'
  python3 scripts/test_modules.py --check || return 1
  local tmp
  tmp="$(mktemp -d)"
  python3 scripts/test_modules.py --emit-md "$tmp/TEST_MODULES.md" >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  cmp -s "$tmp/TEST_MODULES.md" docs/generated/TEST_MODULES.md \
    || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  python3 scripts/test_modules.py --target examples/demo-shop --json >/dev/null || return 1
  echo '  开发模块清单 / MODULE_ID / 发现口径 / 映射渲染 / 目标缺口检查均一致'
}
stage_ontology(){
  note '本体层：投影可复算 / 词表分型 / 三类漂移 / 第七轴'
  python3 scripts/ontology.py check --json >/dev/null || return 1
  local tmp proj out
  tmp="$(mktemp -d)"
  cp -r examples/demo-shop "$tmp/proj" || { rm -rf "$tmp"; return 1; }
  proj="$tmp/proj"
  python3 - "$proj/governance/DECISION_LEDGER.json" <<'PY' || { rm -rf "$tmp"; return 1; }
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d['entries'][0]['status'] = 'rogue-status'
d['status'] = 'bare'
first = d['capability_model']['projects'][0]
d['capability_model']['projects'] = [first, json.loads(json.dumps(first))]
open(p, 'w').write(json.dumps(d, ensure_ascii=False))
PY
  # 注入缺陷后 check 必须失败，diff 必须把三类漂移命名成 ontology 观察
  if python3 scripts/ontology.py check --target "$proj" --json >/dev/null 2>&1; then
    echo '  注入非法状态词/基数违例后本体检查仍通过'
    rm -rf "$tmp"; return 1
  fi
  out="$(python3 scripts/ontology.py diff --target "$proj" --json)" \
    || { rm -rf "$tmp"; return 1; }
  python3 - "$out" <<'PY' || { rm -rf "$tmp"; return 1; }
import json, sys
d = json.loads(sys.argv[1])
kinds = [v['kind'] for v in d['violations']]
assert 'undeclared_value' in kinds, kinds
assert 'cardinality_contradiction' in kinds, kinds
assert 'polyseme_violation' in kinds, kinds
assert d['observations'] and all(o['affected_axis'] == 'ontology' for o in d['observations'])
print(f"  三类漂移均被命名：{len(d['observations'])} 条 ontology 观察")
PY
  local rc=$?
  rm -rf "$tmp"
  return $rc
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
  note '账本不变量（24 条 · pass / fail / na 三态）'
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
  cmp -s templates/registry_codec.py "$DEMO/registry_codec.py" || return 1
  python3 - "$DEMO" <<'PY' || return 1
import json, re, sys
base = sys.argv[1]
html = open(f'{base}/index.html').read()
embed = json.loads(re.search(r'const EMBED = (\{.*?\});\nlet DATA', html, re.S).group(1))
ledger = json.load(open(f'{base}/DECISION_LEDGER.json'))
assert embed == ledger, '看板 EMBED 与账本不一致'
print('  看板 EMBED 与账本一致；模板脚本与示例副本一致')
PY
  python3 scripts/board_contract.py --target examples/demo-shop check --json >/dev/null \
    || { echo '  示例看板骨架与权威模板漂移'; return 1; }
}
stage_scenarios(){
  note '场景矩阵 + 生命周期预检'
  python3 scripts/scenario_matrix.py --check || return 1
  # 与 stage_layout / stage_test_modules 同口径：派生文件必须可由生成器复算。
  # 不能用 git diff --exit-code（与上次提交比），合法重算会被误判成手改派生文件。
  local tmp
  tmp="$(mktemp -d)"
  python3 scripts/scenario_matrix.py --emit-md "$tmp/SCENARIO_MATRIX.md" >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  cmp -s "$tmp/SCENARIO_MATRIX.md" docs/generated/SCENARIO_MATRIX.md \
    || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
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
  echo '  布局定义、渲染同步、示例骨架与第 4 个工具副本均一致'
}
stage_upgrade_access(){
  note '升级与多 Agent 接入（端到端，临时副本）'
  python3 scripts/upgrade.py check || return 1
  python3 scripts/agent_gateway.py check || return 1
  local tmp proj gov fp
  tmp="$(mktemp -d)"
  mkdir -p "$tmp/examples" || { rm -rf "$tmp"; return 1; }
  cp -r examples/demo-shop "$tmp/examples/demo-shop" || { rm -rf "$tmp"; return 1; }
  proj="$tmp/examples/demo-shop"
  gov="$proj/governance"
  python3 scripts/upgrade.py --target "$proj" plan --json >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  python3 scripts/upgrade.py --target "$proj" apply --approved-by gate-bot >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  python3 scripts/upgrade.py --target "$proj" verify --json >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  python3 scripts/ontology.py check --target "$proj" --json >/dev/null \
    || { rm -rf "$tmp"; echo '  升级后第七轴 ontology_digest 未绑定'; return 1; }
  python3 scripts/asset_bundle.py verify --target "$proj" --json >/dev/null \
    || { rm -rf "$tmp"; echo '  升级后专家/技能副本不可用'; return 1; }
  python3 scripts/work_panel.py --target "$proj" check --json >/dev/null \
    || { rm -rf "$tmp"; echo '  升级后节点工作台字段不自洽'; return 1; }
  python3 scripts/route_expert.py --target "$proj" --check-assets --json >/dev/null \
    || { rm -rf "$tmp"; echo '  升级后路由读不到已安装资产'; return 1; }
  python3 scripts/agent_gateway.py --target "$proj" register \
    --agent gate-agent --role loop-executor --approved-by gate-bot --apply >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  fp="$(python3 -c "import json;print(json.load(open('$gov/DECISION_LEDGER.json'))['capability_model']['history']['current_fingerprint'])")"
  python3 scripts/agent_gateway.py --target "$proj" request \
    --agent gate-agent --action claim --code DEMO.API.QUERY.01 \
    --expect-fingerprint "$fp" --apply --json >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  # 未注册 Agent 必须被拒绝（退出码 1），能成功反而是失败
  if python3 scripts/agent_gateway.py --target "$proj" request \
      --agent rogue --action claim --code DEMO.API.QUERY.01 \
      --expect-fingerprint "$fp" --json >/dev/null 2>&1; then
    rm -rf "$tmp"; return 1
  fi
  python3 "$gov/verify_ledger.py" --root "$tmp" \
    --registry "$gov/registry.json" --ledger "$gov/DECISION_LEDGER.json" \
    --board "$gov/index.html" --strict >/dev/null \
    || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  echo '  升级计划/备份/复验、第七轴本体绑定、可用资产、节点工作台、注册批准、写入审计、默认拒绝、26 条三态不变量均通过'
}
stage_contracts(){
  note '资产 / 看板骨架 / 规模预算 / 节点工作台契约'
  python3 scripts/method_assets.py --check >/dev/null || return 1
  python3 scripts/asset_bundle.py --check >/dev/null || return 1
  python3 scripts/route_expert.py --check-assets --json >/dev/null || return 1
  python3 scripts/board_contract.py --target examples/demo-shop check --json >/dev/null || return 1
  python3 scripts/scale_budget.py --target examples/demo-shop --json --check >/dev/null || return 1
  python3 scripts/work_panel.py --target examples/demo-shop check --json >/dev/null || return 1
  python3 scripts/work_panel.py --target examples/demo-shop nodes --json >/dev/null || return 1
  python3 scripts/scale_probe.py --mods 3 --caps 5 --files 40 --events 2 >/dev/null || return 1
  echo '  资产清单齐备、示例骨架与模板一致、工作台自洽、规模预算 ok、基准可复现'
}
stage_feedback(){
  note '反向回流：观察 / triage / 四产物闭环'
  python3 scripts/ledger_feedback.py check --file feedback/observations.jsonl --json >/dev/null \
    || { echo '  观察包闭环校验失败'; return 1; }
  fc="$(python3 scripts/ledger_feedback.py report --file feedback/observations.jsonl --json \
        | python3 -c 'import json,sys;print(json.load(sys.stdin)["feedback_closed"])')" \
    || { echo '  观察包聚合失败'; return 1; }
  [ "$fc" -ge 1 ] || { echo '  本版没有把任何观察收敛成产物'; return 1; }
  a="$(python3 scripts/ledger_feedback.py export --target examples/demo-shop --no-probe --json \
       | python3 -c 'import json,sys;print(json.load(sys.stdin)["sha256"])')"
  b="$(python3 scripts/ledger_feedback.py export --target examples/demo-shop --no-probe --json \
       | python3 -c 'import json,sys;print(json.load(sys.stdin)["sha256"])')"
  [ "$a" = "$b" ] || { echo '  观察导出不幂等'; return 1; }
  echo "  真实观察包 feedback_closed=${fc}，产物引用存在，导出幂等"
}
stage_acceptance(){
  note '验收契约：L1 正文数字 / L2 派生可复算 / L3 观察包 append-only / L4 前置条件'
  # S2 阶段本项预期红灯：先定义「什么算修好」，S3 改权威源后转绿。
  python3 scripts/acceptance.py --check --full
}
stage_preconditions(){
  note 'v1.7.0 前置条件（独立阶段）：G1 规划一致性 / G2 条件化 SOP / G3 activation 占位'
  # 与第 14 阶段同源断言，单列出来是为了让「范围裁剪」不会被整包绿灯掩盖。
  python3 scripts/acceptance.py --preconditions --check --full
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
  run '测试架构' stage_test_modules
  run '证据分层' stage_evidence
  run '账本校验' stage_verify
  run '场景矩阵' stage_scenarios
  run '文件布局' stage_layout
  run '升级与接入' stage_upgrade_access
  run '资产与版面契约' stage_contracts
  run '幂等' stage_idempotence
  run '同步' stage_sync
  run '反向回流' stage_feedback
  run '本体层' stage_ontology
  run '卫生' stage_hygiene
  run '验收契约' stage_acceptance
  run '前置条件' stage_preconditions
fi

printf '\n'
if [ "$FAILURES" -gt 0 ]; then
  printf '质量门禁失败：%d 个阶段未通过\n' "$FAILURES"
  exit 1
fi
printf '质量门禁全绿：测试 / 测试架构 / 证据分层 / 26 条三态不变量 / 场景矩阵 / 文件布局 / 升级与接入 / 资产与工作台契约 / 幂等 / 同步 / 反向回流 / 本体层 / 脱敏 / 文档链接 / 验收契约 / 前置条件\n'
