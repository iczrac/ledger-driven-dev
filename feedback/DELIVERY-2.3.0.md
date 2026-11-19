# DELIVERY 2.3.0 — 派生 issue 闭环 + 方法仓自举

- 版本：v2.3.0
- 日期：2026-11-20
- 状态：方法仓 dogfood 通过 + 主项目推广完成（v2.3.0 全链发布）

## 一、为什么做这一版

v2.2.0 把 `verified` 收紧到 `verified⟺bound`，14 个能力诚实降级为 declared。
但只报警不闭环的红灯会退化成红灯疲劳——没人认领、没人修、没人关。第一性
原理上，一个只报警不收敛的门禁长期必然被无视。

用户的三个判断，逐一验证后成立：
1. **更合理可靠的形态**：issue 必须是账本的派生投影，不能是手工维护的第二
   事实源（手工 = 可删可改 = 「声明权=伪造权」原路返回）。
2. **针对不符合要有反馈 issue**：复用现有 `work_items` + `close_condition`，
   补上「非 bound ⇒ 自动生成 issue」的强制关联。
3. **先 dogfood 再上生产**：方法仓此前不自举（只靠 demo fixture），先用它自己
   的工具治理自己，把误判拦在低成本阶段，再推广到 <主项目>。

## 二、改了什么

- **新工具副本 `derived_issues.py`**（工具数 5→6）：`issue_set = h(binding_status)`。
  每个非 bound 能力恰好一条 `source=derived` 的 issue：固定 id `W-BIND-<CODE>`、
  机器控制 status/severity/close_condition/scope，人工 owner/owner_note/detail
  一律保留；能力转 bound 自动关单并写 resolution；能力回退自动重开。
  `close_condition.kind` 复用 `capability_verified`（v2.2.0 起等价 bound）。
- **不变量 #27**（26→27）`binding_issues_derived`：非 bound 缺 issue、或已 bound
  仍 open、或重复/孤儿派生 issue，均 fail；旧账本无 binding_status 时 na。
- **生成器 `--check` 覆盖 issue**：手删/篡改派生 issue 报漂移，可复算判据扩展为
  「账本 = f(registry, 仓库, 报告)」含 issue 投影。
- **方法仓自举 `governance/`**：6 个主链脚本为能力点，同一套门禁作用于方法仓自己。
- 配套登记：init_project / upgrade TOOLING / scale_probe / check.sh / file_layout /
  method_assets（templates 4→5）/ 测试清单 / ontology 全部同步；文档 CHANGELOG、
  docs/21 补派生 issue 章节。

## 三、dogfood 实证（方法仓治理自己）

用 6 个静态 `from X import ...` 测试的主链脚本建能力 → 绑定门禁判 **bound 6/6**，
测试 330/330 通过，账本 verified 6/6 coverage 1.0，报告 fresh。

再加第 7 个「动态加载测试」能力（`tests/core/test_binding_advisory.py` 用
`spec_from_file_location`，符号分析抓不到 import）作为负向探针：
- 绑定判据判 **unbound** → 诚实降 declared，verified 6/7 coverage 0.86；
- **自动生成** `W-BIND-METHOD-GOV-BINDING-07`（open / high）派生 issue；
- verifier #27 ok=true（派生 1 条 · 非 bound 1 个）；
- `--check` 报「账本 = f(registry, 仓库, 报告)：可复算（含派生 issue）」。

这证明闭环两端都工作：真触达 → bound/verified；抓不到 → 降级 + 可认领 issue；
issue 不可静默删除（#27 + --check 双门禁）。

## 四、复验

- 方法仓单测：`python3 -m unittest discover -s tests` → 328→330 全绿（新增 7 条
  派生 issue 测试 + 5 条 #27/可复算负向测试，先红后绿）
- 方法仓自举报告：330/330 passed，overall=pass
- 自举账本 verifier：25 pass / 0 fail / 2 na（含 #27 ok）
- 自举账本 `--check`：无漂移（含派生 issue）
- ontology：ok=true；模板/自举副本逐字节一致

## 五、边界（不掩盖）

1. 绑定是**必要非充分**条件——有调用关系 ≠ 测对语义；硬门禁只堵「完全无调用
   关系」的伪造，第 7 个能力用动态加载被判 unbound 是判据的已知边界，不是 bug。
2. 派生 issue 的自动关单依赖 binding_status 转 bound；「声明 via 承认间接覆盖」
   或「显式豁免」需人批准并写进 append-only 决策，本次未实现豁免通道——目前
   via1 也会生成 issue（severity=med），需人认领后按既有 work_panel close 处理。
## 五、阶段2 推广到目标项目（用户批准后完成）

- 干净浅 clone → upgrade apply（2.2.0→2.3.0，无阻塞）→ 重绑（报告仍 fresh，
  绑定集只含 `projects/**`，治理工具更新不影响摘要）。
- **18 个**非 bound 能力生成派生 issue（不是 14：14 是从 verified 降下来的，
  另 4 个是原本就 declared 的 no_tests）：11 high（10 unbound + 1 no_impl）、
  7 med（3 via1 + 4 no_tests）。
- 复验：27/27 不变量零放行（#27 对齐 18 条、#25 的 18 个 open 都有 owner_note）、
  `--check` 含 issue 无漂移、upgrade 12/12 pass、完整 CI 门禁
  `27 pass / 0 fail / 0 na（零放行）` + 无漂移 EXIT=0。
- 提交 `79e87e6e`；备份 `/tmp/racos-v230-backup-20261120-052418`；用户工作区
  100 个既有改动全程未碰（干净 clone 操作）。
