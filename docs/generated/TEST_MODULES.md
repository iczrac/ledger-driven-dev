# 测试架构与模块映射（生成物）

> 由 `scripts/test_modules.py` 从 `tests/MODULES.json` 渲染。
> **不要手改**；增删测试请改清单并重跑 `--emit-md`。

共 6 个开发模块 · 26 个 `test_*.py` · 发现口径 `scripts/run_tests.py 的 sorted(tests.rglob('test_*.py'))；unittest discover 作为第二套交叉验证。`。

| 模块 id | 名称 | 覆盖域 | 所属脚本 | 测试文件 |
|---|---|---|---|---|
| `core` | 账本与生成器 | capability_model / history / evidence_tier / verify_ledger | `templates/build_capability_model.py`, `templates/verify_ledger.py`, `scripts/run_tests.py` | `tests/core/test_generation.py`, `tests/core/test_history.py`, `tests/core/test_evidence_tier.py`, `tests/core/test_verify.py`, `tests/core/test_evidence_adapter.py`, `tests/core/test_registry2.py` |
| `adoption` | 新建与存量接入 | greenfield bootstrap / brownfield discovery | `scripts/init_project.py`, `scripts/discover_project.py` | `tests/adoption/test_bootstrap.py`, `tests/adoption/test_discovery.py` |
| `routing` | 专家路由与纪律 | route_expert / skills / scenario_matrix | `scripts/route_expert.py`, `scripts/scenario_matrix.py`, `scripts/ledger_decide.py`, `scripts/ledger_lesson.py` | `tests/routing/test_routing.py`, `tests/routing/test_skills.py`, `tests/routing/test_scenarios.py` |
| `meta` | 元层：升级、接入、生命周期 | upgrade / agent_gateway / lifecycle / file_layout / platform contracts / feedback / ontology / acceptance | `scripts/upgrade.py`, `scripts/agent_gateway.py`, `scripts/lifecycle.py`, `scripts/file_layout.py`, `scripts/ledger_feedback.py`, `scripts/ontology.py`, `scripts/acceptance.py` | `tests/meta/test_upgrade.py`, `tests/meta/test_agent_gateway.py`, `tests/meta/test_lifecycle.py`, `tests/meta/test_layout.py`, `tests/meta/test_platform_contract.py`, `tests/meta/test_feedback.py`, `tests/meta/test_ontology.py`, `tests/meta/test_acceptance.py` |
| `traceability` | 可追溯闭环 | doc rebuild / architecture from docs / git trace / graph compare | `scripts/rebuild_docs.py`, `scripts/architect_from_docs.py`, `scripts/trace_git.py`, `scripts/compare_graphs.py` | `tests/traceability/test_trace_docs.py`, `tests/traceability/test_trace_arch_git.py`, `tests/traceability/test_compare_graphs.py` |
| `views` | 资产可用、工作台与看板视图 | asset_bundle / work_panel / index.html.template / test_modules | `scripts/asset_bundle.py`, `scripts/work_panel.py`, `scripts/board_contract.py`, `scripts/test_modules.py` | `tests/views/test_assets.py`, `tests/views/test_work_panel.py`, `tests/views/test_board_views.py`, `tests/views/test_test_modules.py` |

## 纪律

- 每个测试文件必须有 `MODULE_ID`，且与所在目录、清单三者一致；
- 模块名不得与 Python 标准库冲突，否则 `unittest discover` 会误解析；
- `run_tests.py` 的 `rglob` 与 `unittest discover` 是两套交叉验证，
  两者用例数必须相同（门禁里都跑）；
- `--target P` 可检查被治理项目的能力模块是否缺单测。
