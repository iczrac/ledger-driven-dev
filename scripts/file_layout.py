#!/usr/bin/env python3
"""被治理项目「引入方案后」文件布局的单一事实源。

为什么要单独一份清单
--------------------
「引入后会多出哪些文件、谁写谁改」如果只写在文档里，代码一改就会腐化。
这里把每个目录 / 文件的分层、来源、写入者、写入方式、git 策略与保护机制
定义成数据，并让：
  - ``--check``    自检定义 + 与产出脚本源码交叉验证（防清单漂移）；
  - ``--emit-md``  从同一份定义渲染 docs/generated/FILE_LAYOUT.md；
  - ``--diff``     只读对比任意目标项目现状，报告新增 / 缺失 / 越界文件；
  - ``tests/test_layout.py`` 对以上行为做负向与幂等证明。

关键边界：本清单描述的是**被治理项目（target）**，不是方法论仓库自身。
scripts/ / templates/ / tests/ / docs/01-21 等不会复制进目标项目；
只有 5 个工具脚本副本以 governance/*.py 落地。
v1.2.0 起例外是专家与技能：由 asset_bundle.py 装成 .workbuddy/ 下的
**只读部署副本**（权威源仍在方法论仓库，逐文件 sha256 + 账本绑定）。
账本内的 lifecycle.log / governance_meta / access 等是 **JSON 字段**，
不是独立文件，见 LEDGER_FIELDS。升级备份与写入锁放在项目根的运行时层，
不进 governance/，避免被 --diff 判成第二事实源。

用法
----
    python3 scripts/file_layout.py --check
    python3 scripts/file_layout.py --json
    python3 scripts/file_layout.py --emit-md docs/generated/FILE_LAYOUT.md
    python3 scripts/file_layout.py --diff --target /path/to/project
    python3 scripts/file_layout.py --diff --target /path/to/project --strict --json

退出码：0 正常；2 自检失败 / --strict 下发现必需缺失或越界文件。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCHEMA = "file-layout/1"
ROOT = Path(__file__).resolve().parents[1]

LAYERS = {
    "业务层": "引入前就存在的代码 / 测试 / 文档，方法只规定命名约定，不搬迁、不改写",
    "事实源层": "唯一需要人维护或裁决的输入；所有结论都从这里复算",
    "派生层": "由脚本从事实源重算，禁止手改；改事实源后重跑即可",
    "工具层": "模板复制进目标项目的可执行副本，只读运行，升级靠同步模板",
    "资产层": "专家/技能的只读部署副本，唯一权威源仍是方法论仓库 tag",
    "草稿层": "存量接入时的临时候选，人工确认前不得成为事实源",
    "运行时层": "升级备份与写入互斥锁；不属于事实源、不参与结论复算、不进 governance/",
}

ORIGINS = {"preexisting": "引入前可能已有", "new": "引入方案后新增"}
PRESENCES = {
    "required": "治理骨架必需",
    "on-demand": "跑对应命令后才出现（不出现属正常）",
    "brownfield": "仅存量接入路径出现",
    "preexisting": "原有资产，不强制",
}
WRITES = {
    "manual": "人手写 / 经脚本按纪律写入",
    "bootstrap": "初始化时写一次，默认跳过既有文件",
    "rewrite": "每次运行全量重写，可覆盖",
    "write-if-absent": "默认跳过既有文件，--force 才覆盖",
    "append-only": "只能追加，不得删改既有记录",
    "state-field": "账本内状态字段，随账本一起持久化",
    "read-only": "只读取证，脚本不写它",
}
COMMITS = {"yes": "建议提交 git", "optional": "可提交（便于离线审计）或 CI 重跑",
           "no": "不建议提交（本地临时产物）"}

# path, kind, layer, origin, presence, owner, producer, write, commit,
# guard, purpose, note, expect(在 producer 源码里必须出现的字面量)
ENTRIES: list[dict] = [
    # ---------------- 业务层：方法不改变它 ----------------
    dict(path="src/", kind="dir", layer="业务层", origin="preexisting", presence="preexisting",
         owner="开发者", producer="", write="manual", commit="yes", guard="registry.impls 路径校验",
         purpose="实现代码。registry 的 impls 必须指向这里真实存在的文件。", note="", expect=""),
    dict(path="tests/", kind="dir", layer="业务层", origin="preexisting", presence="preexisting",
         owner="开发者", producer="", write="manual", commit="yes",
         guard="evidence_binding 源码摘要",
         purpose="单元测试。文件名与 unit_test 声明匹配，测试报告绑定其内容摘要。",
         note="测试源码改动后 verified 会自动回落 declared，需重跑测试报告。", expect=""),
    dict(path="docs/", kind="dir", layer="业务层", origin="preexisting", presence="preexisting",
         owner="开发者", producer="", write="manual", commit="yes", guard="doc_index 路径校验",
         purpose="人工文档根目录；其下再分 plans / test_records / generated。", note="", expect=""),
    dict(path="docs/plans/", kind="dir", layer="业务层", origin="preexisting", presence="preexisting",
         owner="开发者", producer="", write="manual", commit="yes", guard="HINT 文件名匹配",
         purpose="规划文档 <HINT>_PLAN.md / *_ROADMAP.md，是 L1 契约证据之一。",
         note="HINT 必须与 registry 的能力 hints 一致，否则生成器识别不到。", expect=""),
    dict(path="docs/test_records/", kind="dir", layer="业务层", origin="preexisting",
         presence="preexisting", owner="开发者", producer="", write="manual", commit="yes",
         guard="HINT 文件名匹配",
         purpose="测试记录 <HINT>_TEST_RECORD.md，是 L4 运行验证证据之一。",
         note="与 docs/generated/ 区分：这里是人写的实测记录，那里是机器渲染。", expect=""),

    # ---------------- 事实源层 ----------------
    dict(path="governance/", kind="dir", layer="事实源层", origin="new", presence="required",
         owner="init_project.py", producer="scripts/init_project.py", write="bootstrap",
         commit="yes", guard="scenario_guard 越界文件检查",
         purpose="治理目录：事实源、派生报告与工具副本都收敛在此，不另建管理项目。",
         note="此目录出现清单外的自制报告 / 第二份账本会被 --diff 报为越界。", expect="governance"),
    dict(path="governance/registry.json", kind="file", layer="事实源层", origin="new",
         presence="required", owner="人（唯一手写清单）", producer="scripts/init_project.py",
         write="manual", commit="yes", guard="registry_impls_exist / component_paths_exist",
         purpose="能力注册表：项目信息、模块清单、impls / hints / unit_test 声明。全项目唯一需手填的清单。",
         note="新建为空清单；存量接入来自人工确认后的 registry.draft.json。多人同改仍需 git 合并。",
         expect="registry.json"),
    dict(path="governance/DECISION_LEDGER.json", kind="file", layer="事实源层", origin="new",
         presence="required", owner="生成器 / 决策脚本 / 生命周期脚本",
         producer="scripts/init_project.py", write="rewrite", commit="yes",
         guard="26 条不变量 / --expect-fingerprint CAS / frozen 冻结 / 看板 EMBED 同步",
         purpose="单一事实源：entries 决策、capability_model 派生结果、history、lessons、lifecycle 全在这里。",
         note="可以写 entries（经 ledger_decide.py），但 level / completion / history / EMBED 一律自动派生，禁止手改。",
         expect="DECISION_LEDGER.json"),

    # ---------------- 派生层 ----------------
    dict(path="governance/index.html", kind="file", layer="派生层", origin="new",
         presence="required",
         owner="build_capability_model.py / lifecycle.py / upgrade.py / board_contract.py",
         producer="templates/build_capability_model.py", write="rewrite", commit="yes",
         guard="board_embed_synced 不变量 + 去 EMBED 后的骨架 sha256（board_contract.py）",
         purpose="可视化看板；EMBED 与账本逐字节等价，CSS/DOM/JS 骨架与权威模板一致、按 PAGE_SIZE 分批渲染。",
         note="lifecycle.py 改状态时同步 EMBED；禁止在项目里改样式，换版面要改模板并发版再由 upgrade 归一。",
         expect="index.html"),
    dict(path="governance/test_report.json", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="run_tests.py", producer="scripts/run_tests.py",
         write="rewrite", commit="optional",
         guard="evidence_binding 逐文件 sha256 / --strict-evidence",
         purpose="机器可读测试报告，schema ledger-test-report/1；是 verified 证据的唯一来源。",
         note="报告绑定测试源码内容摘要；源码一改就判 stale，verified 回落 declared。",
         expect="test_report.json"),
    dict(path="governance/TARGET_ARCHITECTURE.json", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="architect_from_docs.py",
         producer="scripts/architect_from_docs.py", write="write-if-absent", commit="optional",
         guard="置信度 warnings",
         purpose="从规范文档抽取的目标架构：目标 / 模块 / 能力编码 / 依赖 / target_level。",
         note="结构化抽取而非自然语言理解；差异只报告，不自动回写 registry。",
         expect="TARGET_ARCHITECTURE.json"),
    dict(path="governance/GIT_TRACE.json", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="trace_git.py", producer="scripts/trace_git.py",
         write="write-if-absent", commit="optional", guard="只读 git log --name-only",
         purpose="提交 → 变更路径 → 模块 / 能力编码 / 决策 id / 历史事件序号的映射。",
         note="不信任 commit message，只认真实变更路径；force-push 重写历史无法本地证明。",
         expect="GIT_TRACE.json"),
    dict(path="governance/GRAPH_DIFF.json", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="compare_graphs.py", producer="scripts/compare_graphs.py",
         write="write-if-absent", commit="optional", guard="五态比对 + next_queue",
         purpose="规划图 vs 实际图的机器可读差异，附开发顺序、执行专家与前置条件。",
         expect="GRAPH_DIFF.json"),
    dict(path="governance/CODE_INDEX.json", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="code_index.py", producer="scripts/code_index.py",
         write="write-if-absent", commit="optional", guard="四段式编码一致性",
         purpose="能力编码 ↔ 文档 / 测试 / 实现代码 / 决策 / 历史事件 / git 提交的全链路索引。",
         note="编码是跨 artifact 的唯一身份证，不要另起一套编号。", expect="CODE_INDEX.json"),
    dict(path="docs/generated/", kind="dir", layer="派生层", origin="new", presence="on-demand",
         owner="rebuild_docs.py / compare_graphs.py", producer="scripts/rebuild_docs.py",
         write="write-if-absent", commit="yes", guard="可逐字节复现 / 无绝对路径",
         purpose="机器渲染的规范化文档目录，与人工 docs/ 物理隔离，避免误改生成物。",
         note="需要长期人工补充时请换文件名，不要手改这里的生成物。", expect="generated"),
    dict(path="docs/generated/PROJECT_BRIEF.md", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="rebuild_docs.py", producer="scripts/rebuild_docs.py",
         write="write-if-absent", commit="yes", guard="默认不覆盖",
         purpose="规范化项目简报：目标、范围、现状、状态词、边界。", note="",
         expect="PROJECT_BRIEF.md"),
    dict(path="docs/generated/MODULE_MAP.md", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="rebuild_docs.py", producer="scripts/rebuild_docs.py",
         write="write-if-absent", commit="yes", guard="默认不覆盖",
         purpose="模块地图：模块 → 目录 → 能力编码，回答「东西在哪」。", note="",
         expect="MODULE_MAP.md"),
    dict(path="docs/generated/CAPABILITY_INDEX.md", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="rebuild_docs.py", producer="scripts/rebuild_docs.py",
         write="write-if-absent", commit="yes", guard="默认不覆盖",
         purpose="能力索引：编码 → 文档 / 测试 / 代码 / 决策 / 等级。", note="",
         expect="CAPABILITY_INDEX.md"),
    dict(path="docs/generated/GRAPH_DIFF.md", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="compare_graphs.py", producer="scripts/compare_graphs.py",
         write="write-if-absent", commit="yes", guard="默认不覆盖",
         purpose="规划图与实际图差异的人类可读报告与开发顺序。", note="",
         expect="GRAPH_DIFF.md"),

    # ---------------- 草稿层（仅存量接入） ----------------
    dict(path="governance/registry.draft.json", kind="file", layer="草稿层", origin="new",
         presence="brownfield", owner="discover_project.py / 人",
         producer="scripts/discover_project.py", write="write-if-absent", commit="optional",
         guard="只读发现 / 默认不覆盖 / 需人工精简",
         purpose="存量项目盘点草稿，schema registry-draft/1。人工确认后才被 adopt 消费。",
         note="草稿不是事实源；重复跑 discover 不会覆盖它。", expect="registry.draft.json"),
    dict(path="governance/ADOPTION_REPORT.md", kind="file", layer="草稿层", origin="new",
         presence="brownfield", owner="discover_project.py",
         producer="scripts/discover_project.py", write="write-if-absent", commit="optional",
         guard="只读发现 / 截断与无测试告警",
         purpose="人类可读的接入盘点报告：候选模块、能力点、置信度、风险与下一步。",
         note="", expect="ADOPTION_REPORT.md"),

    # ---------------- 工具层（模板副本） ----------------
    dict(path="governance/build_capability_model.py", kind="file", layer="工具层", origin="new",
         presence="required", owner="init_project.py（复制模板）",
         producer="scripts/init_project.py", write="bootstrap", commit="yes",
         guard="check.sh 模板/示例逐字节同步 / --no-generator 可跳过",
         purpose="生成器副本：从 registry + 证据重算账本与看板。",
         note="不要在目标项目里改这份副本；升级方法论后同步 templates/ 版本。",
         expect="build_capability_model.py"),
    dict(path="governance/verify_ledger.py", kind="file", layer="工具层", origin="new",
         presence="required", owner="init_project.py（复制模板）",
         producer="scripts/init_project.py", write="bootstrap", commit="yes",
         guard="26 条不变量 / 模板同步",
         purpose="校验器副本：回答「账本内部坏没坏」。",
         note="与 scenario_guard.py 分工：后者回答「现在能不能动它」，未复制进目标项目。",
         expect="verify_ledger.py"),
    dict(path="governance/registry_codec.py", kind="file", layer="工具层", origin="new",
         presence="required", owner="init_project.py（复制模板）",
         producer="scripts/init_project.py", write="bootstrap", commit="yes",
         guard="唯一 code_namespace / cap_code / normalize_projects / iter_caps",
         purpose="registry schema/2 唯一编码与容器归一化契约，供生成器和校验器共同消费。",
         note="禁止在目标项目里改写；code 规则只在本方法的权威模板维护。",
         expect="registry_codec.py"),
    dict(path="governance/run_tests.py", kind="file", layer="工具层", origin="new",
         presence="required", owner="init_project.py（复制 scripts/）",
         producer="scripts/init_project.py", write="bootstrap", commit="yes",
         guard="报告含源码绑定摘要",
         purpose="测试报告生成器副本，产出 governance/test_report.json。",
         note="工具副本之一：让项目脱离本仓库也能独立复算证据（v2.1.2 起共 5 个）。",
         expect="run_tests.py"),
    dict(path="governance/binding_advisory.py", kind="file", layer="工具层", origin="new",
         presence="required", owner="init_project.py（复制模板）",
         producer="scripts/init_project.py", write="bootstrap", commit="yes",
         guard="符号级绑定 advisory / 模板同步",
         purpose="证据绑定 advisory 副本：查「声明的测试」与「声明的实现」之间有无调用关系。",
         note="shadow 门禁：只晒 [UNBOUND] 不否决；由生成器在重算时调用，独立成模块是让生成器主体保持在模块大小硬限之下。",
         expect="binding_advisory.py"),

    # ---------------- 资产层：专家 / 技能的项目级只读副本 ----------------
    dict(path=".workbuddy/", kind="dir", layer="资产层", origin="new",
         presence="on-demand", owner="asset_bundle.py", producer="scripts/asset_bundle.py",
         write="write-if-absent", commit="optional",
         guard="asset_bundle.py verify 逐文件 sha256 / manifest 整包摘要",
         purpose="平台项目级 Agent 资产目录；升级 M7 后才有内容，权威源仍是方法论仓库。",
         note="这里只放由治理升级安装的副本；用户自己放的技能不属于治理清单，不会被删除。",
         expect=".workbuddy"),
    dict(path=".workbuddy/skills/", kind="dir", layer="资产层", origin="new",
         presence="on-demand", owner="asset_bundle.py", producer="scripts/asset_bundle.py",
         write="rewrite", commit="optional",
         guard="frontmatter name 与目录名一致 / 逐字节副本校验",
         purpose="可被 Agent 平台直接加载的技能副本，每个技能一个 <name>/SKILL.md。",
         note="禁止在项目内编辑；改技能要改方法论仓库并发版，再由 M7 重新安装。",
         expect="skills"),
    dict(path=".workbuddy/experts/", kind="dir", layer="资产层", origin="new",
         presence="on-demand", owner="asset_bundle.py", producer="scripts/asset_bundle.py",
         write="rewrite", commit="optional",
         guard="frontmatter name 与目录名一致 / 逐字节副本校验",
         purpose="专家包副本，每个专家一个 <name>/EXPERT.md；路由优先消费这份已安装资产。",
         note="路由卡若引用的专家缺文件，--check-assets 会 fail-closed 报 incomplete。",
         expect="experts"),
    dict(path="governance/ASSET_MANIFEST.json", kind="file", layer="派生层", origin="new",
         presence="on-demand", owner="asset_bundle.py", producer="scripts/asset_bundle.py",
         write="rewrite", commit="yes",
         guard="逐文件 sha256 + 整包 digest + 账本 installed_assets 绑定",
         purpose="已安装资产的只读清单；证明副本与权威源逐字节一致、没有多余旧版本。",
         note="不是第二事实源：它只记录 sha256，不含规则正文；权威源是方法论仓库 tag。",
         expect="ASSET_MANIFEST.json"),

    # ---------------- 运行时层：升级与多 Agent 接入的副产物 ----------------
    dict(path=".ledger-upgrade/", kind="dir", layer="运行时层", origin="new",
         presence="on-demand", owner="upgrade.py", producer="scripts/upgrade.py",
         write="write-if-absent", commit="no",
         guard="manifest 只存相对路径 / 路径不含 ..",
         purpose="升级备份根目录；跑过 upgrade.py apply 后才出现。",
         note="备份是时间戳快照，不是活跃状态；放在项目根而不在 governance/，避免分裂事实源。",
         expect=".ledger-upgrade"),
    dict(path=".ledger-upgrade/backups/", kind="dir", layer="运行时层", origin="new",
         presence="on-demand", owner="upgrade.py", producer="scripts/upgrade.py",
         write="write-if-absent", commit="no", guard="rollback 需 --approved-by",
         purpose="每次升级一个目录：<UTC>-<账本摘要前 8 位>/manifest.json + 被改文件的副本。",
         note="manifest.json 列相对路径与 sha256；rollback 按清单逐文件恢复并记录到 upgrade_log。",
         expect="backups"),
    dict(path=".ledger-write.lock", kind="file", layer="运行时层", origin="new",
         presence="on-demand", owner="agent_gateway.py", producer="scripts/agent_gateway.py",
         write="write-if-absent", commit="no", guard="fcntl.flock 锁内重读账本并重新判定",
         purpose="多 Agent 写入网关的 OS 级互斥锁文件，保证读-判-写原子。",
         note="瞬态协调文件，不是事实源；无 fcntl 的平台降级为告警（见 E6 边界）。",
         expect=".ledger-write.lock"),
]

# 统一补齐可选字段，避免新增条目时漏写导致 KeyError。
for _entry in ENTRIES:
    for _key in ("owner", "producer", "guard", "note", "expect"):
        _entry.setdefault(_key, "")

# 账本内字段：不是文件，但最容易被误当成 governance/ 下的独立文件。
LEDGER_FIELDS: list[dict] = [
    dict(path="capability_model", owner="build_capability_model.py", write="rewrite",
         purpose="能力等级、完成度、组件树、文档索引、next_queue 的派生结果；禁止手改。"),
    dict(path="history.events", owner="build_capability_model.py", write="append-only",
         purpose="状态指纹链；末事件指纹必须等于当前能力模型指纹。"),
    dict(path="entries", owner="ledger_decide.py / ledger_lesson.py", write="manual",
         purpose="决策 D-NNN；人裁决，AI 只能新增 proposed。"),
    dict(path="lessons.items / lessons.candidates", owner="ledger_lesson.py / 生成器",
         write="manual / 派生", purpose="已确认经验与自动识别的候选，任务卡只引用 confirmed。"),
    dict(path="lifecycle / lifecycle.log", owner="lifecycle.py", write="state-field / append-only",
         purpose="冻结、归档、批准人、状态变更日志。**不是 governance/lifecycle.log 文件**。"),
    dict(path="retired_caps / execution.claims", owner="lifecycle.py", write="state-field",
         purpose="退役编码登记与任务领用锁，保证编码不复用、同码不被两个执行者同时领用。"),
    dict(path="provenance", owner="init_project.py", write="bootstrap",
         purpose="接入来源（template / 草稿相对路径）、模式与意图，外部绝对路径自动脱敏。"),
    dict(path="governance_meta / upgrade_log", owner="upgrade.py",
         write="state-field / append-only",
         purpose="版本七轴、已应用迁移、工具 sha256 与升级/回滚日志。**不是 UPGRADE_LOG.md 文件**。"),
    dict(path="governance_meta.method_assets / board_skeleton / installed_assets",
         owner="upgrade.py", write="state-field",
         purpose="整包资产摘要、看板骨架摘要，以及项目级已安装副本的逐文件绑定；三者任一漂移都要重新批准升级。"),
    dict(path="work_items", owner="work_panel.py", write="state-field",
         purpose="节点级 TODO / issue 的唯一写入点；scope 可指向项目、模块或四段式能力编码。"),
    dict(path="test_results", owner="work_panel.py sync-tests", write="state-field",
         purpose="测试报告的可验证投影（source_sha256 绑定原报告）；供工作台显示模块/组件级逐用例结果。"),
    dict(path="access / access.audit", owner="agent_gateway.py",
         write="state-field / append-only",
         purpose="Agent 名册、编码租约、revision 与写入审计。**不是 AGENTS.yaml 或独立审计日志**。"),
]

# 方法论仓库自身：不会进入被治理项目。
NOT_IN_TARGET: list[dict] = [
    dict(path="experts/、skills/（权威源）", reason="方法论仓库里的专家与技能**原文**不进项目源码；"
                                   "v1.2.0 起由 asset_bundle.py 把逐字节只读副本装到 .workbuddy/，"
                                   "整包摘要写进 governance_meta.method_assets、副本清单写进 installed_assets。"),
    dict(path="scripts/、templates/、tests/", reason="方法论自身的工具、模板与测试；只有 3 个脚本副本落到 governance/。"),
    dict(path="docs/01-21、docs/STANDARD.md", reason="方法论文档，属于本仓库而非被治理项目。"),
    dict(path="docs/generated/SCENARIO_MATRIX.md、FILE_LAYOUT.md、TEST_MODULES.md",
         reason="本仓库的机器渲染矩阵；目标项目只会得到 docs/generated/ 下那 4 份项目级文档。"),
    dict(path="examples/、.github/workflows/、CHANGELOG.md、RELEASE_CHECKLIST.md",
         reason="示例、CI 与发布资产，属于方法论仓库。"),
    dict(path="全仓 .git/", reason="git 元数据；trace_git.py 只读取证，不写入、不重写历史。"),
]

ABS_RE = re.compile(r"(?:/Users/|/home/|/private/var/|(?<![A-Za-z0-9+.\-])[A-Za-z]:[\\/](?![/]))")
IGNORE_NAMES = {"__pycache__", ".DS_Store", ".git"}
IGNORE_SUFFIX = (".pyc", ".pyo", ".tmp", ".swp")


def validate() -> list[str]:
    """自检清单定义，并交叉验证「产出脚本源码里确实写着这个文件名」。"""
    errs: list[str] = []
    seen: set[str] = set()
    paths = {e["path"] for e in ENTRIES}
    for e in ENTRIES:
        p = e["path"]
        if p in seen:
            errs.append(f"重复路径：{p}")
        seen.add(p)
        if p.startswith("/") or ".." in Path(p).parts or ABS_RE.search(p):
            errs.append(f"路径必须为项目根相对：{p}")
        is_dir = p.endswith("/")
        if e["kind"] != ("dir" if is_dir else "file"):
            errs.append(f"kind 与路径形态不符：{p}")
        for key, allowed in (("layer", LAYERS), ("origin", ORIGINS),
                             ("presence", PRESENCES), ("write", WRITES), ("commit", COMMITS)):
            if e[key] not in allowed:
                errs.append(f"{p} 的 {key} 取值非法：{e[key]}")
        if e["layer"] == "派生层" and e["write"] == "manual":
            errs.append(f"派生层不得人工维护：{p}")
        if not e["purpose"]:
            errs.append(f"缺少目录含义：{p}")
        if ABS_RE.search(e.get("purpose", "") + e.get("note", "")):
            errs.append(f"说明里含机器绝对路径：{p}")
        if e["kind"] == "file":
            if not e["producer"]:
                errs.append(f"文件缺少产出脚本：{p}")
            else:
                src = ROOT / e["producer"]
                if not src.is_file():
                    errs.append(f"产出脚本不存在：{e['producer']}（{p}）")
                elif e["expect"] and e["expect"] not in src.read_text(encoding="utf-8"):
                    errs.append(f"清单与代码漂移：{e['producer']} 未出现 {e['expect']}（{p}）")
            if e["expect"] and not e["producer"]:
                errs.append(f"expect 需配合 producer：{p}")
        if e["kind"] == "dir" and e["producer"]:
            src = ROOT / e["producer"]
            if not src.is_file():
                errs.append(f"目录产出脚本不存在：{e['producer']}")
    # 目录项存在性
    for e in ENTRIES:
        if e["kind"] == "file":
            parent = str(Path(e["path"]).parent).replace("\\", "/") + "/"
            if parent != "./" and parent not in paths:
                errs.append(f"缺少父目录条目：{e['path']} → {parent}")
    if not any(e["layer"] == "事实源层" and e["write"] == "manual" for e in ENTRIES):
        errs.append("必须存在唯一手写清单 registry.json")
    for f in LEDGER_FIELDS:
        if not f["purpose"]:
            errs.append(f"账本字段缺少含义：{f['path']}")
    return errs


def summary() -> dict:
    from collections import Counter
    return {
        "schema": SCHEMA,
        "total": len(ENTRIES),
        "by_layer": dict(Counter(e["layer"] for e in ENTRIES)),
        "by_origin": dict(Counter(e["origin"] for e in ENTRIES)),
        "by_presence": dict(Counter(e["presence"] for e in ENTRIES)),
        "required": [e["path"] for e in ENTRIES if e["presence"] == "required"],
        "added_by_method": [e["path"] for e in ENTRIES if e["origin"] == "new"],
        "ledger_fields": len(LEDGER_FIELDS),
        "not_in_target": len(NOT_IN_TARGET),
    }


def diff(target: Path) -> dict:
    """只读对比目标项目：不创建、不修改、不删除任何文件。"""
    files = [e for e in ENTRIES if e["kind"] == "file"]
    rows: list[dict] = []
    for e in ENTRIES:
        p = target / e["path"]
        exists = p.is_dir() if e["kind"] == "dir" else p.is_file()
        if exists:
            status = "present"
        elif e["presence"] == "required":
            status = "gap-required"
        elif e["presence"] == "brownfield":
            status = "n/a-greenfield"
        elif e["presence"] == "on-demand":
            status = "not-run"
        else:
            status = "absent-preexisting"
        rows.append({"path": e["path"], "layer": e["layer"], "origin": e["origin"],
                     "presence": e["presence"], "status": status, "exists": exists})

    # governance/ 下的清单外文件 = 可能出现第二事实源，报警
    known = {e["path"] for e in ENTRIES}
    unexpected: list[str] = []
    gov = target / "governance"
    if gov.is_dir():
        for p in sorted(gov.rglob("*")):
            if not p.is_file() or any(part in IGNORE_NAMES for part in p.parts):
                continue
            if p.name.endswith(IGNORE_SUFFIX):
                continue
            rel = p.relative_to(target).as_posix()
            if rel not in known:
                unexpected.append(rel)

    ledger = {}
    ledger_path = gov / "DECISION_LEDGER.json"
    if ledger_path.is_file():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            ledger = {}
    gaps = [r["path"] for r in rows if r["status"] == "gap-required"]
    phase = ("bootstrap" if gaps else
             "governed" if ledger.get("capability_model") else "skeleton")
    lifecycle = (ledger.get("lifecycle") or {}).get("state", "active") if isinstance(ledger, dict) else "active"

    return {
        "schema": "file-layout-diff/1",
        "target_label": ".",  # 不输出绝对路径
        "phase": phase,
        "lifecycle": lifecycle,
        "counts": {
            "total": len(rows),
            "present": sum(1 for r in rows if r["exists"]),
            "gap_required": len(gaps),
            "not_run": sum(1 for r in rows if r["status"] == "not-run"),
        },
        "added_present": [r["path"] for r in rows
                          if r["origin"] == "new" and r["exists"]],
        "missing_required": gaps,
        "unexpected": unexpected,
        "rows": rows,
        "hint": ("先跑 init_project.py 建立骨架" if phase == "bootstrap" else
                 "骨架在但尚未生成能力模型，跑 build_capability_model.py" if phase == "skeleton" else
                 "治理循环已就绪；写入前跑 scenario_guard.py"),
    }


def render_md() -> str:
    lines = [
        "# FILE_LAYOUT · 引入方案后的文件布局",
        "",
        "> 本文件由 `scripts/file_layout.py` 从布局定义渲染；请勿手改。",
        f"> schema `{SCHEMA}` · 条目 {len(ENTRIES)} · "
        f"引入后新增 {sum(1 for e in ENTRIES if e['origin'] == 'new')} 项 · "
        f"账本内字段 {len(LEDGER_FIELDS)} 项。",
        "",
        "## 分层含义",
        "",
        "| 层 | 含义 |",
        "|---|---|",
        *(f"| {k} | {v} |" for k, v in LAYERS.items()),
        "",
        "## 目录与文件清单",
        "",
        "「写入」列：manual 人写 / bootstrap 初始化写一次 / rewrite 全量重算 / "
        "write-if-absent 默认跳过 / append-only 只追加 / read-only 只读。",
        "",
        "| 路径 | 层 | 来源 | 出现时机 | 谁写 | 写入 | 手改 | git | 含义 / 保护 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for e in ENTRIES:
        editable = "可" if e["write"] == "manual" else "禁"
        meaning = e["purpose"]
        if e["guard"]:
            meaning += f"　保护：{e['guard']}。"
        if e["note"]:
            meaning += f"　注：{e['note']}"
        lines.append(
            f"| `{e['path']}` | {e['layer']} | {ORIGINS[e['origin']]} | "
            f"{PRESENCES[e['presence']]} | {e['owner']} | `{e['write']}` | {editable} | "
            f"{COMMITS[e['commit']]} | {meaning} |"
        )
    lines += [
        "",
        "## 账本内字段（不是 governance/ 下的独立文件）",
        "",
        "| 字段 | 写入者 | 方式 | 含义 |",
        "|---|---|---|---|",
        *(f"| `{f['path']}` | {f['owner']} | {f['write']} | {f['purpose']} |"
          for f in LEDGER_FIELDS),
        "",
        "## 不会进入被治理项目的内容",
        "",
        "| 方法论仓库路径 | 原因 |",
        "|---|---|",
        *(f"| `{x['path']}` | {x['reason']} |" for x in NOT_IN_TARGET),
        "",
        "## 复算方式",
        "",
        "```bash",
        "python3 scripts/file_layout.py --check",
        "python3 scripts/file_layout.py --diff --target /path/to/project --strict",
        "```",
        "",
        "`--check` 会逐条核对产出脚本源码中是否仍写着该文件名，",
        "清单与代码漂移时直接失败；`--diff` 全程只读。",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="自检布局定义与代码一致性")
    ap.add_argument("--json", action="store_true", help="输出定义统计 JSON（或与 --diff 合用）")
    ap.add_argument("--emit-md", help="渲染 Markdown 到指定路径")
    ap.add_argument("--diff", action="store_true", help="只读对比目标项目现状")
    ap.add_argument("--target", default=".", help="--diff 的目标项目根目录")
    ap.add_argument("--strict", action="store_true",
                    help="--diff 下发现必需缺失或越界文件时返回 2")
    args = ap.parse_args(argv)

    if args.check:
        errs = validate()
        if errs:
            print("\n".join("  - " + e for e in errs), file=sys.stderr)
            return 2
        print(f"布局定义自检通过：{len(ENTRIES)} 个条目 / {len(LEDGER_FIELDS)} 个账本内字段")
        return 0

    if args.emit_md:
        errs = validate()
        if errs:
            print("\n".join("  - " + e for e in errs), file=sys.stderr)
            return 2
        p = Path(args.emit_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_md(), encoding="utf-8")
        print(f"已生成 {p}")
        return 0

    if args.diff:
        target = Path(args.target).expanduser().resolve()
        if not target.is_dir():
            print(f"目标目录不存在：{args.target}", file=sys.stderr)
            return 2
        d = diff(target)
        if args.json:
            print(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            c = d["counts"]
            print(f"阶段 {d['phase']} · 生命周期 {d['lifecycle']} · "
                  f"已在位 {c['present']}/{c['total']} · 未跑命令 {c['not_run']}")
            if d["missing_required"]:
                print("缺失必需：" + ", ".join(d["missing_required"]))
            if d["unexpected"]:
                print("治理目录越界文件：" + ", ".join(d["unexpected"]))
            print("下一步：" + d["hint"])
        if args.strict and (d["missing_required"] or d["unexpected"]):
            return 2
        return 0

    s = summary()
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"布局 {s['total']} 项 · 引入后新增 {len(s['added_by_method'])} 项 · "
              + " / ".join(f"{k} {v}" for k, v in s["by_layer"].items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
