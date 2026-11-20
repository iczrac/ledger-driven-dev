#!/usr/bin/env bash
# 黄金范例：一条人话意图走完整条治理链，全程只读、不写任何项目文件。
#
# 链路：复述门 → 路由 → 自动编排 → 批准包 → 来源投影 → 完成定义
#   "实现 DEMO.API.QUERY.01 的测试代码" 这句人话，
#   机器不会猜着往下走，而是先复述、再路由、再展开分工、标出人批准点，
#   最后把每条 issue/decision 的 [AI推断]/[人确认] 来源与任务完成定义摊开给人看。
#   注：措辞须命中路由意图模式；"补齐测试记录"这类未识别说法会被 fail-closed
#   要求澄清（这是 P0 的正确行为，不是缺陷）。
#
# 用法：bash examples/golden-walkthrough/run.sh
# 前提：在 ledger-driven-dev 方法仓根目录执行。
# 纪律：所有命令都是只读（--json / --check / --dry-run），无 --apply、无写盘。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# 真实存在的意图样本：结构化复述声明（能力码锚定到 demo 账本）。
INTENT_FILE="examples/golden-walkthrough/intent.json"
TARGET="examples/demo-shop"
STEP=0
step() { STEP=$((STEP+1)); echo; echo "═══ 步骤 $STEP · $1 ═══"; }

step "复述门：把人话变成结构化声明并用真实 registry/账本锚定"
python3 scripts/intent_restate.py --target "$TARGET" --intent-file "$INTENT_FILE" \
  --json | python3 -c 'import sys,json; d=json.load(sys.stdin); print("verdict =", d["verdict"]); print("checks =", len(d["checks"])); [print("  -", c["id"], c["status"]) for c in d["checks"]]'

step "路由：确定唯一负责人与交接链"
python3 scripts/route_expert.py --target "$TARGET" --intent "实现 DEMO.API.QUERY.01 的测试代码" \
  --json | python3 -c 'import sys,json; d=json.load(sys.stdin); r=d["route"]; print("expert =", r["expert"], "| confidence =", r["confidence"]); print("chain =", "→".join(r["handoff"]["chain"]))'

step "自动编排：沿交接链展开逐跳契约与分类命令（dry-run 零执行）"
python3 scripts/expert_run.py --target "$TARGET" --intent "实现 DEMO.API.QUERY.01 的测试代码" \
  --json | python3 -c 'import sys,json; d=json.load(sys.stdin); print("verdict =", d["verdict"]); print("summary =", d["summary"]); [print("  [%d] %s → %s"%(s["index"],s["expert"],s["next_expert"] or "终点")) for s in d["chain"]]'

step "批准包：只列出需要人 --approved-by 的写入点"
python3 scripts/expert_run.py --target "$TARGET" --intent "实现 DEMO.API.QUERY.01 的测试代码" \
  --json | python3 -c 'import sys,json; d=json.load(sys.stdin); b=d["approval_bundle"]; print("需批准命令 =", b["count"]); [print("  -", x["command"]) for x in b["commands"][:5]]; print("note =", b["note"])'

step "来源投影：issue/decision 按 [AI推断]/[人确认] 分组展示"
python3 scripts/provenance_view.py --target "$TARGET" --kind issue --json | \
  python3 -c 'import sys,json; d=json.load(sys.stdin); print("summary =", d["summary"]); [print("  -", i["id"], "|", i["ai_inferred"]["label"].split("]")[0]+"]", len(i["ai_inferred"]["fields"]), "字段 /", i["human_confirmed"]["label"].split("]")[0]+"]", len(i["human_confirmed"]["fields"]), "字段") for i in d["issues"][:3]]'

step "完成定义：从任务卡既有字段派生 definition_of_done（不写回账本）"
python3 scripts/provenance_view.py --target "$TARGET" --kind task --json | \
  python3 -c 'import sys,json; d=json.load(sys.stdin); t=d["tasks"][0]; print("任务 =", t["code"], "→", t["target_level"]); print("完成判据 =", t["criteria"]); print("达标条件 =", t["satisfied_when"]); print("来源 =", t["provenance"])'

echo
echo "═══ 黄金范例完成 ═══"
echo "全链路只读：6 步无 --apply、无写盘；同输入可复算。"
echo "这证明：全 AI 驱动 = 机器自治编排 + 人只在批准点拍板，不是拆掉所有门。"
