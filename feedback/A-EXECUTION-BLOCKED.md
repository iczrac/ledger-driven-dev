# 选项 A 执行记录：写盘前阻断（未 apply）

> 用户指令：「先做 a」。
> A 的定义：零摘要成本、不发版；由人批准一次真实证据绑定（`import-report --apply` + `sync-tests --apply`），使 `P` 至少一条能力升为 `verified`。
> **裁定：A 在写盘前被发现会触发 47 个能力的等级回退，已停止，未对 `P` 写入任何字节。**

## 一、先给结论

1. **真实 CI 报告已经拿到**：10 个能力引用单测、**19 passed / 0 fail / 0 error / 0 skip**，JUnit 由项目 venv 的 pytest 原生产出。
2. **合规报告已经拿到**：19 个用例全部映射到账本白名单内真实存在的测试文件路径，`status/id/seconds` 一字未改；`evidence_binding.inputs=2041`、`source_digest=dd38f38264f4e33a`。
3. **dry-run 全链通过**：`import-report --dry-run` 与 `build_capability_model.py --dry-run --strict-evidence` 均正常返回，报告被采信、`freshness=(True, 'fresh')`。
4. **但 apply 会破坏账本**：插桩发现生成器对 47 个能力调用 `judge_tier()` 时传入的 `unit_test` **全部为空列表**；直接跑 `build()` 得到的 level 分布是 `L2:46 / L0:1`，而当前账本是 `L5:20 / L3:22 / L2:5`。**若 apply，L5 与 L3 能力会被批量降级，且 verified 仍是 0%——既没拿到绿灯，又毁掉了既有等级。**
5. 因此按「诚实 > 绿灯」「先确认数据正常再重建快照」的纪律**停止写盘**，转报人裁决。

## 二、真实执行过的动作（全部只读或写临时目录）

| 动作 | 结果 |
|---|---|
| `pytest --collect-only -q`（10 个能力引用文件） | 19 tests collected in 2.02s |
| 真实运行同一批（唯一 `--basetemp` 规避沙箱 `tmp_path` 竞态） | **19 passed in 2.32s** |
| JUnit XML sha256 | `0d145e674094b4a323e34b6f…` |
| JUnit `classname` → 账本 `unit_tests[].path` 白名单映射 | 19/19 命中，映射 10 个真实文件，0 unmapped |
| 合规报告 sha256 | `240a4b48383ed0c2f38e86b8…` |
| `import-report --dry-run --adapter ledger --source-dir …` | `cases=19 / overall=pass / source_digest=dd38f38264f4e33a` |
| `load_test_report()` + `check_freshness()` 直调 | `loaded=True / overall=pass / inputs=2041 / freshness=(True,'fresh')` |

合规映射的定义：**只补 `cases[].file` 这一个字段**，值取自账本 `capability_model` 中真实存在的能力单测白名单；`status` / `id` / `seconds` 完全来自真实 JUnit，未新增、未删改任何用例。这不构成伪造。

## 三、阻断根因（插桩实证）

包装 `judge_tier()` 后对 47 次调用取样：

```
calls: 47
  uts sample: [] -> declared
  uts sample: [] -> declared
verified calls: 0
```

再包装 `judge_level()`，定位到扫描入口：

```
proj_root = P               （仓库根，非子项目根）
test_root = P/tests         exists=False
hints = ['<CODE>.DATA.READY.01', ...]   （能力代码，不是文件名片段）
unit_test = []
```

根因有两层：

- **`registry.json` 的 `project.unit_test_dir = "tests"`，而 `P` 根目录没有 `tests/`**（真实测试在 `projects/<app>/tests/unit`）。因此 `test_root.exists()` 为假，`ev["unit_test"]` 恒空。
- **即使把 `unit_test_dir` 改成 `projects/<app>/tests/unit`，内存验证仍是 `declared:47 / verified_coverage=0`**：因为 `hints` 是能力代码（形如 `<CODE>.DATA.READY.01`），与测试文件名（形如 `test_data_readiness_*.py`）没有任何公共子串，`judge_level()` 的文件名匹配永远命中不了。

更关键的是**旁边的连带退化**：同一批内存验证中，三种 `unit_test_dir` 取值下的 level 分布全部是 `L2:46 / L0:1`，而账本当前是 `L5:20 / L3:22 / L2:5`。这说明 `registry.json` 的路径契约与 `P` 的真实 monorepo 布局存在**系统性失配**，不只是单测一项。重跑生成器不是「升一级 verified」，而是「整体重算并降级」。

## 四、为什么没有 apply（诚实清单）

- **未执行** `import-report --apply`、`sync-tests --apply`、`build_capability_model.py` 的写盘模式；三者都只做了只读预演。
- **未创建** `P/governance/test_report.json`；`test_results` 仍 `null`；`activation.state` 仍 `unbound`；47 个能力仍全部 `declared`。
- 主仓账本 sha256 执行前后同为 `1094451c223cb2a7…`；level 分布仍 `L5:20 / L3:22 / L2:5`。
- **17 条待写盘动作的人批准未被使用**：用户说「先做 a」使 A 具备授权，但 A 的前提是「写入后账本不退化」。该前提被证伪，故不写。
- 上一份 `feedback/P1-ADAPTATION-AUDIT.md` 提出的两处缺口之外，本轮**新增发现两处主仓侧缺口**（`unit_test_dir` 失配、`hints` 与文件名不匹配），且后者会连带 L 级回退。四者共同说明：P1 不能靠「补一份报告」解决。

## 五、下一步需要重新裁决

原二选一的判断需要更新：

- **A 已在写盘前被证伪**，不是「先补一份报告就能升 verified」；继续强行 apply 只会降级账本。
- **B（v1.8.0）范围应扩大**：除方法论仓侧两处适配外，还必须处理主仓 `registry.json` 的路径契约与能力→单测映射（hints），并且要保证「重算不降级」——例如分级迁移而非整表重算、写前快照比对、L 级回退硬门禁。这属于主仓数据迁移 + 方法论仓发版，**必须单独授权、备份、人批准**。
- 若只想验证链路而不碰账本：临时副本里已证成 `24 pass / all_active=true`（见 `P1-ADAPTATION-AUDIT.md`），不必在 `P` 上重演。

## 六、提交与作用域

仅新增本文件，位于 `feedback/`（`ZERO` 作用域，不在 `ASSET_GROUPS`）。**不改 ASSET 字节、不改 `P` 账本、不升版本、不打 tag**；`tag v1.7.0` 的资产字节与 `ca1f49e` 保持一致。所有真实报告与 JUnit 只存在于临时探针目录，未入库。
