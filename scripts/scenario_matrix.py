#!/usr/bin/env python3
"""场景定义的单一事实源：文档表格与测试探针都从这里派生。

为什么不把覆盖情况写在文档里
----------------------------
「我们支持这个场景」是一句会腐化的叙述。这里把每个场景的
id / 公理 / 期望行为 / 探针函数写死，由
  - tests/test_scenarios.py 逐个跑探针证明期望成立；
  - --emit-md 从同一份定义渲染 docs/generated/SCENARIO_MATRIX.md。
覆盖状态因此是**复算结果**，不是作者声明。

状态语义
--------
covered    有代码路径 + 测试探针证明
partial    有降级/告警，但不构成完整闭环（文档须写明残差）
by-design  刻意不做，属于方法边界（文档须写明理由）
gap        已知缺漏，本期未实现（文档须写明代价与后续条件）

用法
----
    python3 scripts/scenario_matrix.py
    python3 scripts/scenario_matrix.py --json
    python3 scripts/scenario_matrix.py --check
    python3 scripts/scenario_matrix.py --emit-md docs/generated/SCENARIO_MATRIX.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

AXIOMS = {
    "A1": "状态完备：在哪 / 去哪 / 谁在改 / 凭什么 / 谁批准",
    "A2": "证据有效：结论来自可复算证据，且对当前源码有效",
    "A3": "单点写入：同一事实只有一个写入点",
    "A4": "时间可逆：历史不可篡改，能检测并发覆盖与中断",
    "A5": "未知即停止：版本 / 路径 / 完整性存疑时 fail-closed",
    "A6": "边界闭合：进入 / 冻结 / 归档 / 退役 / 失效都有出口",
}
STATUSES = {
    "covered": "已覆盖（有探针）",
    "partial": "部分覆盖（有降级与告警，残差见文档）",
    "by-design": "边界内刻意不做（附理由）",
    "gap": "已知缺漏（本期未实现）",
}

# id, 轴, 场景, 公理, 状态, 期望行为, 探针, 最短流程, 备注
SCENARIOS: list[dict] = [
    # L 生命周期
    dict(id="L1", axis="生命周期", name="空目录新建项目", axiom="A6", status="covered",
         expected="greenfield-architect 建最小骨架，缺 registry 时不得声称完成度",
         probe="test_routing.RoutingTest.test_greenfield_empty_dir",
         flow=["route_expert.py --target P", "init_project.py --target P --mode greenfield"],
         note=""),
    dict(id="L2", axis="生命周期", name="历史项目无损接入", axiom="A6", status="covered",
         expected="只读盘点产出草稿，人工确认前不覆盖任何既有文件",
         probe="test_discovery + test_bootstrap",
         flow=["discover_project.py --target P --dry-run", "discover_project.py --target P",
               "init_project.py --target P --mode adopt --from-draft ..."],
         note=""),
    dict(id="L3", axis="生命周期", name="稳态迭代", axiom="A1", status="covered",
         expected="SCAN→SELECT→PLAN→EXECUTE→VERIFY 可循环，重跑幂等",
         probe="test_generation + test_history", flow=["build_capability_model.py --root P"],
         note=""),
    dict(id="L4", axis="生命周期", name="半成品（有账本缺 registry）", axiom="A5", status="covered",
         expected="路由到 ledger-steward 补齐唯一手写清单，不重建 history",
         probe="test_routing.RoutingTest.test_partial_state",
         flow=["route_expert.py --target P", "补齐 governance/registry.json"],
         note=""),
    dict(id="L5", axis="生命周期", name="账本 JSON 损坏", axiom="A5", status="covered",
         expected="冻结写入，先备份再人工修复，verify 通过前不得继续",
         probe="test_scenarios.ScenarioProbeTest.test_corrupt_ledger_blocks_writes",
         flow=["scenario_guard.py --target P --strict", "备份并修复账本", "verify_ledger.py --strict"],
         note=""),
    dict(id="L6", axis="生命周期", name="发布窗口冻结", axiom="A6", status="covered",
         expected="lifecycle freeze 后 guard 阻止所有写动作；生成器返回 2",
         probe="test_lifecycle.LifecycleTest.test_freeze_blocks_generator",
         flow=["lifecycle.py --target P freeze --reason ...",
               "lifecycle.py --target P unfreeze --approved-by <人>"],
         note=""),
    dict(id="L7", axis="生命周期", name="归档与移交", axiom="A6", status="covered",
         expected="archive 需人工批准，转为不可写终态；只读取证仍可用",
         probe="test_lifecycle.LifecycleTest.test_archive_is_terminal",
         flow=["lifecycle.py --target P archive --approved-by <人>",
               "verify_ledger.py --root P --strict", "打包 governance/ 交付"],
         note=""),
    dict(id="L8", axis="生命周期", name="冻结期误写 / AI 自行解冻", axiom="A1", status="covered",
         expected="unfreeze 无 approved-by 被拒绝；批准人写入 lifecycle.approved_by",
         probe="test_lifecycle.LifecycleTest.test_unfreeze_requires_human_approval",
         flow=["lifecycle.py --target P unfreeze --approved-by <人>"], note=""),
    dict(id="L9", axis="生命周期", name="能力退役与编码不复用", axiom="A6", status="covered",
         expected="retire 登记四段式编码 + 取代关系；仍活跃则 guard block",
         probe="test_scenarios.ScenarioProbeTest.test_retired_cap_conflict_blocks",
         flow=["lifecycle.py --target P retire --code ... --reason ...",
               "从 registry.json 移除该能力", "build_capability_model.py --root P"],
         note=""),
    dict(id="L10", axis="生命周期", name="模块拆分 / 重命名", axiom="A4", status="partial",
         expected="编码稳定不随名称变化，但无自动 rename 映射表",
         probe="test_generation",
         flow=["保留编码，仅改 registry.name", "重跑生成器"],
         note="残差：跨仓/跨项目引用无法自动重写，需人工 new → old 映射并写入决策"),
    # C 变更语义
    dict(id="C1", axis="变更", name="新增能力", axiom="A1", status="covered",
         expected="等级从证据重算，未达 L5 自动生成 next_action",
         probe="test_generation", flow=["编辑 registry.json", "重跑生成器"], note=""),
    dict(id="C2", axis="变更", name="等级上调", axiom="A2", status="covered",
         expected="补齐契约/实现/单测/记录才升级；指纹链追加事件",
         probe="test_history", flow=["补证据", "重跑生成器", "verify_ledger.py"], note=""),
    dict(id="C3", axis="变更", name="等级回落 / 证据消失", axiom="A2", status="covered",
         expected="证据文件删除后等级回落，历史事件记录降级信号",
         probe="test_generation + test_history", flow=["重跑生成器", "查看 GRAPH_DIFF"], note=""),
    dict(id="C4", axis="变更", name="declared → verified", axiom="A2", status="covered",
         expected="只有报告 overall=pass 且匹配单测才升级",
         probe="test_evidence_tier.EvidenceTierTest.test_generator_with_report_upgrades_matching_caps",
         flow=["run_tests.py --dir tests --out governance/test_report.json",
               "build_capability_model.py --root P --test-report ..."], note=""),
    dict(id="C5", axis="变更", name="报告丢失 / 整体失败", axiom="A5", status="covered",
         expected="全部回落 declared，不保留旧 verified 徽章",
         probe="test_evidence_tier.EvidenceTierTest.test_failed_report_never_upgrades",
         flow=["重跑生成器（不带报告）"], note=""),
    dict(id="C6", axis="变更", name="报告过期（源码改了但没重跑测试）", axiom="A2", status="covered",
         expected="源码摘要不匹配 → 报告不予采信，verified 回落 declared",
         probe="test_scenarios.ScenarioProbeTest.test_stale_report_downgrades_evidence",
         flow=["run_tests.py → 生成账本", "修改测试文件", "重跑生成器（同一报告）"],
         note="v0.8.0 前是假绿灯：judge_tier 只按文件名匹配"),
    dict(id="C7", axis="变更", name="决策取代 / 撤回", axiom="A4", status="covered",
         expected="supersedes 双向一致，取代链连续",
         probe="test_verify", flow=["ledger_decide.py", "verify_ledger.py"], note=""),
    dict(id="C8", axis="变更", name="目标架构变更", axiom="A1", status="partial",
         expected="compare_graphs 显示 planned_only/actual_only 差异",
         probe="test_compare_graphs",
         flow=["architect_from_docs.py", "compare_graphs.py"],
         note="残差：差异只报告，不自动回写 registry；避免文档误读直接改动事实源"),
    dict(id="C9", axis="变更", name="外部数据源 / 依赖版本变化", axiom="A2", status="by-design",
         expected="不绑定具体数据源；由项目自己的测试报告表达",
         probe="test_evidence_tier", flow=["在被测项目内跑 run_tests.py"],
         note="理由：方法论项目不应持有外部系统凭据或版本知识"),
    # P 并发与协作
    dict(id="P1", axis="并发", name="单人连续重跑（幂等）", axiom="A4", status="covered",
         expected="状态未变不追加历史事件，看板 EMBED 保持同步",
         probe="test_generation + check.sh stage_idempotence",
         flow=["build_capability_model.py --root P（两次）"], note=""),
    dict(id="P2", axis="并发", name="两 Agent 同时写账本", axiom="A3", status="covered",
         expected="读取时指纹与当前不符 → CAS 拒绝写入，退出码 2",
         probe="test_scenarios.ScenarioProbeTest.test_cas_rejects_stale_write",
         flow=["读 current_fingerprint", "build_capability_model.py --expect-fingerprint FP"],
         note=""),
    dict(id="P3", axis="并发", name="读后写漂移（人工手改账本）", axiom="A4", status="covered",
         expected="guard 报 concurrent_write block；history 指纹链可发现篡改",
         probe="test_scenarios.ScenarioProbeTest.test_fingerprint_drift_detected",
         flow=["scenario_guard.py --target P --expect-fingerprint FP --strict"], note=""),
    dict(id="P4", axis="并发", name="长任务中断后恢复", axiom="A4", status="covered",
         expected="claim/release 记录领用者；超时锁在 guard 中告警",
         probe="test_lifecycle.LifecycleTest.test_claim_release",
         flow=["lifecycle.py claim --code ... --actor ai-1",
               "（中断）scenario_guard.py --json", "lifecycle.py release"], note=""),
    dict(id="P5", axis="并发", name="同一任务被两个 Agent 领用", axiom="A3", status="covered",
         expected="第二次不同 actor 的 claim 被拒绝",
         probe="test_lifecycle.LifecycleTest.test_duplicate_claim_rejected",
         flow=["lifecycle.py claim --code ... --actor ai-2（应失败）"], note=""),
    dict(id="P6", axis="并发", name="CI 与本地结论不一致", axiom="A5", status="partial",
         expected="同一份 check.sh 消除口径差异；环境差异仍需显式声明",
         probe="check.sh", flow=["本地 bash scripts/check.sh", "CI 同一命令"],
         note="残差：Python 版本 / 时区 / 文件系统大小写敏感未做矩阵测试"),
    # T 时间与审计
    dict(id="T1", axis="时间", name="首次运行（无账本）", axiom="A6", status="covered",
         expected="生成器创建空账本骨架并写入首个历史事件",
         probe="test_generation", flow=["build_capability_model.py --root P"], note=""),
    dict(id="T2", axis="时间", name="跨版本升级 / 迁移", axiom="A5", status="covered",
         expected="兼容版本走 plan→备份→人批准 apply→verify→重新取证；"
                  "不兼容账本仍 fail-closed，不猜结构",
         probe="test_upgrade.UpgradeTest.test_apply_is_approved_backed_up_and_verifiable "
               "+ test_scenarios.ScenarioProbeTest.test_unsupported_version_blocks",
         flow=["upgrade.py --target P plan --json",
               "upgrade.py --target P apply --approved-by <人>",
               "upgrade.py --target P verify --json", "执行 post_upgrade 11 步"],
         note="迁移只加字段，不改 history.events，因此不追加历史事件；"
              "真正的 ledger_version 数据迁移仍需人工写专用方案"),
    dict(id="T3", axis="时间", name="历史回溯 / 外部取证", axiom="A4", status="covered",
         expected="事件指纹自证、末事件指纹 == 当前能力模型指纹",
         probe="test_verify + test_history", flow=["verify_ledger.py --strict --json"], note=""),
    dict(id="T4", axis="时间", name="git 历史被 rebase / force push 重写", axiom="A4", status="partial",
         expected="浅克隆被 guard 告警；trace_git 不信任 commit message",
         probe="test_trace_arch_git", flow=["scenario_guard.py --json", "trace_git.py"],
         note="残差：无法从本地证明远端未强制推送；需外部签名/服务端保护"),
    dict(id="T5", axis="时间", name="报告时间戳跨时区", axiom="A2", status="covered",
         expected="新鲜度用内容摘要判定，不依赖时间戳比较",
         probe="test_scenarios.ScenarioProbeTest.test_freshness_uses_content_not_clock",
         flow=["run_tests.py", "build_capability_model.py --test-report ..."], note=""),
    # E 环境
    dict(id="E1", axis="环境", name="非 git 目录", axiom="A5", status="covered",
         expected="guard 告警；trace_git 退出码 2，不伪造提交关联",
         probe="test_trace_arch_git", flow=["trace_git.py --target P"], note=""),
    dict(id="E2", axis="环境", name="没有测试 / 没有单测", axiom="A2", status="covered",
         expected="全部能力保持 declared，verified 覆盖率为 0",
         probe="test_evidence_tier", flow=["build_capability_model.py --root P"], note=""),
    dict(id="E3", axis="环境", name="没有文档 / 文档是自由散文", axiom="A5", status="covered",
         expected="architect_from_docs 置信度降级为 low 并给 warnings",
         probe="test_trace_arch_git", flow=["architect_from_docs.py --target P"], note=""),
    dict(id="E4", axis="环境", name="只读文件系统", axiom="A6", status="by-design",
         expected="guard / verify / trace / route 可只读运行；生成器需要写权限",
         probe="test_scenarios.ScenarioProbeTest.test_guard_is_read_only",
         flow=["scenario_guard.py --target P --json"],
         note="理由：生成与校验分离，审计者无需写权限"),
    dict(id="E5", axis="环境", name="超大仓库扫描截断", axiom="A5", status="covered",
         expected="扫描达上限标记 truncated，guard 告警，不声称全量覆盖",
         probe="test_discovery + test_scenarios.ScenarioProbeTest.test_truncated_scan_warns",
         flow=["scenario_guard.py --max-files N --json"], note=""),
    dict(id="E6", axis="环境", name="非 UTF-8 / Windows 路径", axiom="A5", status="partial",
         expected="JSON/HTML 统一 UTF-8，路径相对化；未做跨平台 CI 矩阵",
         probe="test_trace_docs",
         flow=["保持源码 UTF-8", "避免绝对路径写入账本"],
         note="残差：Windows 换行与大小写敏感差异未在 CI 覆盖"),
    dict(id="E7", axis="环境", name="monorepo 多项目 / 跨仓依赖", axiom="A1", status="gap",
         expected="当前 registry.project.root 只描述单个项目根",
         probe="", flow=["每个项目各自 governance/，用外层脚本聚合"],
         note="缺漏：无跨项目依赖图与联合门禁；需要独立的 workspace 层，本期未做"),
    # F 失败与授权
    dict(id="F1", axis="失败", name="未批准就执行 / 越权写账本", axiom="A1", status="covered",
         expected="ledger_decide 只写 proposed；解冻/归档必须人工批准",
         probe="test_skills + test_lifecycle", flow=["ledger_decide.py", "verify_ledger.py"], note=""),
    dict(id="F2", axis="失败", name="人驳回提议 / 优先级争议", axiom="A3", status="by-design",
         expected="条目留 deferred/proposed，AI 不替人决定业务优先级",
         probe="test_skills", flow=["账本条目置 deferred 并写明理由"],
         note="理由：优先级是业务判断，不应用脚本推断"),
    dict(id="F3", axis="失败", name="测试偶发失败（flaky）", axiom="A2", status="by-design",
         expected="报告如实记录 fail，不自动重试",
         probe="test_evidence_tier", flow=["run_tests.py --out report.json"],
         note="理由：自动重试会把不稳定测试伪装成通过；稳定性应在被测项目内解决"),
    dict(id="F4", axis="失败", name="绝对路径 / 来源项目名词泄露", axiom="A5", status="covered",
         expected="guard block；check.sh 卫生阶段扫描全仓",
         probe="test_scenarios.ScenarioProbeTest.test_absolute_path_blocks",
         flow=["bash scripts/check.sh"], note=""),
    dict(id="F5", axis="失败", name="模板与示例副本漂移", axiom="A5", status="covered",
         expected="check.sh 同步阶段逐字节比较；guard 告警",
         probe="check.sh stage_sync", flow=["bash scripts/check.sh"], note=""),
    dict(id="F6", axis="失败", name="看板 EMBED 与账本不一致", axiom="A3", status="covered",
         expected="verify 的 board_embed_synced 失败；guard 告警",
         probe="test_verify", flow=["重跑生成器"], note=""),
    dict(id="F7", axis="失败", name="多人同时改 registry.json", axiom="A3", status="partial",
         expected="网关对依赖手写清单的动作要求 --expect-registry-sha，"
                  "内容摘要漂移即拒绝（检测，不合并）",
         probe="test_agent_gateway.GatewayTest.test_registry_cas_detects_concurrent_edit",
         flow=["agent_gateway.py status 取 registry_sha256",
               "request ... --expect-registry-sha <sha>", "git 人工合并冲突"],
         note="残差：只检测漂移，不自动合并；无 workspace 层时跨项目联合门禁仍缺（E7）"),
    # U 升级（规则本身随时间变化）
    dict(id="U1", axis="时间", name="工具副本落后于权威模板", axiom="A5", status="covered",
         expected="plan 报 drifted/missing 并要求 M3 同步；verify 的 tool_hashes 不通过",
         probe="test_upgrade.UpgradeTest.test_plan_detects_tool_drift",
         flow=["upgrade.py --target P plan --json",
               "upgrade.py --target P apply --approved-by <人>"],
         note="check.sh 只同步本仓库模板/示例，管不到已交付项目的工具副本，这一层由 upgrade 补"),
    dict(id="U2", axis="时间", name="升级后证据未重新绑定", axiom="A2", status="covered",
         expected="verify 报 evidence_rebaseline warn，upgrade_complete=false；"
                  "post_upgrade 要求先重跑报告再 --strict-evidence 生成",
         probe="test_upgrade.UpgradeTest.test_verify_flags_stale_evidence",
         flow=["run_tests.py --out governance/test_report.json",
               "build_capability_model.py --test-report ... --strict-evidence"],
         note="工具源码变化会让 evidence_binding 失配，verified 回落 declared 是正确行为，"
              "危险的是没人重跑"),
    # G 接入（参与者维度，v0.9.0 之前被隐含在 A3 里）
    dict(id="G1", axis="接入", name="未注册 / 越权 Agent 写账本", axiom="A3", status="covered",
         expected="默认拒绝：access 缺失、agent 未登记、角色无权、scopes 越界均 deny 且不写盘",
         probe="test_agent_gateway.GatewayTest.test_unregistered_and_unauthorized_denied",
         flow=["upgrade.py apply 建立 access", "register --approved-by <人>",
               "agent_gateway.py request --json（默认 dry-run）"],
         note="权限从 EXPERT.md 的散文移到写入口的九道门"),
    dict(id="G2", axis="接入", name="两个 Agent 并发写同一能力", axiom="A4", status="covered",
         expected="flock 锁内重读、指纹 CAS、编码租约与 revision 共同阻止静默覆盖",
         probe="test_agent_gateway.GatewayTest.test_lease_blocks_concurrent_agent",
         flow=["status 取 fingerprint / registry_sha",
               "request --expect-fingerprint <fp> --apply"],
         note="同一能力编码在租约 TTL 内只属于先登记的 Agent；超时由人清理"),
    dict(id="G3", axis="接入", name="Agent 自我批准 / 自行提权", axiom="A1", status="covered",
         expected="register 的 approved_by 不得等于 agent；unfreeze/archive 必须人批准",
         probe="test_agent_gateway.GatewayTest.test_self_approval_and_self_register_denied",
         flow=["register --approved-by <人>", "request --action unfreeze --approved-by <人>"],
         note="权限授予者 ≠ 被授权者，批准人写入 access.audit 与 lifecycle.approved_by"),
    dict(id="G4", axis="接入", name="Agent 直接调用底层脚本绕过网关", axiom="A5", status="by-design",
         expected="网关是策略执行点，不是 OS 沙箱；有 shell 仍可绕过",
         probe="test_agent_gateway.GatewayTest.test_policy_point_boundary_is_declared",
         flow=["平台只把 agent_gateway.py 注册为写工具", "CI 只接受带 audit 的产物"],
         note="理由：强隔离需要容器 / 只读挂载 / 文件系统权限，超出纯文本方法范围；"
              "刻意不在脚本里伪装成安全边界"),
    # U / F / S：资产、版面与规模（v1.1.0）
    dict(id="U3", axis="时间", name="专家 / 技能 / 模板 / 文档资产漂移", axiom="A2",
         status="covered",
         expected="整包资产摘要写进账本；任一资产变化即 plan 要求 M5 重新批准，verify 不再宣布完成",
         probe="test_platform_contract.AssetsTest.test_upgrade_binds_assets_and_detects_drift",
         flow=["method_assets.py --check", "upgrade.py --target P plan --json",
               "upgrade.py --target P apply --approved-by <人>"],
         note="资产随方法论仓库 tag 升级、不复制进目标项目；绑定的是摘要，不是第二份文件"),
    dict(id="F8", axis="失败", name="项目手改看板 CSS / DOM 形成差异化版面", axiom="A3",
         status="covered",
         expected="去 EMBED 后的骨架 sha256 漂移；plan 列入 M6，归一化后数据段仍与账本等价",
         probe="test_platform_contract.BoardTest.test_drift_is_part_of_the_upgrade_plan",
         flow=["board_contract.py --target P check --json",
               "upgrade.py --target P apply --approved-by <人>",
               "board_contract.py --target P check"],
         note="要换样式只能改方法论模板并发版，再由升级推到所有项目"),
    dict(id="S1", axis="规模", name="大项目账本体积 / 历史事件 / DOM 超预算", axiom="A6",
         status="covered",
         expected="scale_budget.py 按单一阈值表报 ok/warn/exceed，模板按 PAGE_SIZE 分批渲染，"
                  "治理层文件数保持固定",
         probe="test_platform_contract.BudgetTest.test_thresholds_flag_oversized_project",
         flow=["scale_budget.py --target P --json --check",
               "scale_probe.py --mods 50 --caps 20 --files 1500 --json",
               "file_layout.py --diff --target P --strict"],
         note="基准：1000 能力 / 1500 文件 / 80 事件 → 生成器 4.4s，账本 9.6 MiB，治理文件仍为 4"),
    dict(id="S2", axis="规模", name="生成器全量重算的成本", axiom="A2", status="partial",
         expected="可复现基准 + 阈值告警；超阈值由人决定拆项目或归档，不做静默降级",
         probe="test_platform_contract.BudgetTest.test_probe_shows_file_count_stays_fixed",
         flow=["scale_probe.py --json", "scale_budget.py --target P --check"],
         note="残差：生成器按能力逐个扫 docs / tests，接近 O(能力 × 文件)，没有增量索引；"
              "触发升级条件：超过 1 万能力或 2 万文件且门禁耗时不可接受时，"
              "再引入缓存/分片，同时必须保持同一份账本可复算"),
]


def validate(scenarios: list[dict] = SCENARIOS) -> list[str]:
    errors: list[str] = []
    ids = [s["id"] for s in scenarios]
    if len(ids) != len(set(ids)):
        errors.append("场景 id 重复")
    for s in scenarios:
        for key in ("id", "axis", "name", "axiom", "status", "expected", "probe", "flow", "note"):
            if key not in s:
                errors.append(f"{s.get('id','?')} 缺字段 {key}")
        if s["axiom"] not in AXIOMS:
            errors.append(f"{s['id']} 公理非法：{s['axiom']}")
        if s["status"] not in STATUSES:
            errors.append(f"{s['id']} 状态非法：{s['status']}")
        if s["status"] == "covered" and not s["probe"]:
            errors.append(f"{s['id']} 标为 covered 却没有探针")
        if s["status"] == "gap" and not s["note"]:
            errors.append(f"{s['id']} 标为 gap 却没有说明代价")
    return errors


def summary(scenarios: list[dict] = SCENARIOS) -> dict:
    by_status = Counter(s["status"] for s in scenarios)
    by_axis = Counter(s["axis"] for s in scenarios)
    by_axiom = Counter(s["axiom"] for s in scenarios)
    return {"total": len(scenarios), "by_status": dict(by_status),
            "by_axis": dict(by_axis), "by_axiom": dict(by_axiom),
            "coverage": round((by_status["covered"] + 0.5 * by_status["partial"])
                              / max(1, len(scenarios)), 3)}


BADGE = {"covered": "已覆盖", "partial": "部分", "by-design": "边界", "gap": "缺漏"}


def render_md(scenarios: list[dict] = SCENARIOS) -> str:
    s = summary(scenarios)
    lines = [
        "# 场景覆盖矩阵（生成物）",
        "",
        "> 由 `scripts/scenario_matrix.py` 从场景定义渲染。**不要手改本文件**；",
        "> 修改场景请改 `SCENARIOS`，再重跑 `--emit-md`。",
        "",
        f"共 {s['total']} 个场景 · 有效覆盖率 {s['coverage']:.1%} "
        f"（covered 计 1，partial 计 0.5，by-design 与 gap 计 0）。",
        "",
        "| 状态 | 数量 | 语义 |", "|---|---:|---|",
    ]
    for k, label in STATUSES.items():
        lines.append(f"| {BADGE[k]} | {s['by_status'].get(k, 0)} | {label} |")
    lines += ["", "## 场景逐项", "",
              "| ID | 轴 | 场景 | 公理 | 状态 | 期望行为 | 探针 |",
              "|---|---|---|---|---|---|---|"]
    for x in scenarios:
        lines.append(f"| {x['id']} | {x['axis']} | {x['name']} | {x['axiom']} | "
                     f"{BADGE[x['status']]} | {x['expected']} | `{x['probe'] or '—'}` |")
    lines += ["", "## 最短流程（playbook）", ""]
    for axis in sorted({x["axis"] for x in scenarios}):
        lines += [f"### {axis}", ""]
        for x in [y for y in scenarios if y["axis"] == axis]:
            lines.append(f"- **{x['id']} {x['name']}**（{BADGE[x['status']]}）："
                         + " → ".join(f"`{c}`" for c in x["flow"]))
            if x["note"]:
                lines.append(f"  - {x['note']}")
        lines.append("")
    lines += ["## 公理索引", ""]
    for k, v in AXIOMS.items():
        lines.append(f"- **{k}** {v}（{s['by_axiom'].get(k, 0)} 个场景）")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="输出统计 JSON")
    ap.add_argument("--check", action="store_true", help="自检场景定义完整性")
    ap.add_argument("--emit-md", help="渲染 Markdown 到指定路径")
    args = ap.parse_args(argv)

    if args.check:
        errs = validate()
        if errs:
            print("\n".join(errs), file=sys.stderr)
            return 2
        print(f"场景定义自检通过：{len(SCENARIOS)} 个场景")
        return 0
    if args.emit_md:
        p = Path(args.emit_md)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(render_md(), encoding="utf-8")
        print(f"已生成 {p}")
        return 0
    s = summary()
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"场景 {s['total']} 个 · " +
              " / ".join(f"{BADGE[k]} {v}" for k, v in s["by_status"].items()) +
              f" · 有效覆盖率 {s['coverage']:.1%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
