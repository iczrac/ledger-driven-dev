# DELIVERY 2.1.2 — 证据绑定与资产对账

- 日期：2026-11-19
- 状态：已发布（tag v2.1.2）
- 批准：用户批准「②③ 合成一个 2.1.2 补丁落盘；work_items.owner 立规矩」

## 一、这版解决什么

v2.1.0 之后账本可复算（`--check` 无漂移），但两个「写了就信」的死角仍在：

1. **配对靠猜**：`caps[].tests` 与 `caps[].impl` 的对应是按文件名关键词
   配的。词面碰撞（同名 registry、同名 ledger）会把 A 能力的测试挂到
   B 能力上——路径层检查（存在 + 已入库）完全看不见。
2. **资产摘要不对账**：安装器（`asset_bundle`）与路由器（`route_expert`）
   对同一份 28 文件资产各算各的摘要（`924ab50…` vs `688131ca…`），
   后者算完只打印不比对，`ok:true` 只代表 frontmatter 合法——
   v2.1.0 删掉的「自证」在资产层复发。

## 二、交付内容

### 1. 符号级证据绑定 advisory（shadow 门禁）

- `SymbolIndex`：测试 import 的名字沿 `__init__.py` 再导出链解析到定义
  文件；多别名按项目就近消歧（`projects/<x>` 内不串味）；
- 三种真实耦合都判得出：直接 import / 汇总导出（`from src.pkg import X`）/
  一跳编排层（via1，附桥接文件）；
- `[BIND]` 摘要 + 逐条 `[UNBOUND]` 告警；`--binding-report` 机器可读；
- **不改 level/tier、不影响退出码**。判据先晒、人审验证、再谈硬门禁。

主仓实测（47 能力）：bound 29 / via1 3 / unbound 10 / no_impl 1 / no_tests 4。
14 个 verified 能力的证据映射存疑（unbound 10 + no_impl 1 + via1 3）。

### 2. 资产摘要统一与对账

- 摘要规范化统一为 `sha256-files-v1`（安装前缀 + 按路径排序 + 尾换行）：
  从权威源算与从安装副本算得到同一个值（`924ab50…`，与清单、账本一致）；
- `--check-assets` 逐文件 sha + 整包摘要与清单对账，任一不符 fail-closed；
  无清单显式 `manifest_checked=false`，不假装验过；
- 负向证明：篡改 `ledger-verify/SKILL.md` 一个字节，逐文件与整包同时报警。

### 3. 两条新不变量（24 → 26）

- **#25 `work_items_owned`**：未完结（open/doing/blocked）必须有 owner 或
  owner_note；done 不追溯。AI 不凭空指派 owner——让缺口可见，不替人填；
- **#26 `installed_assets_binding`**：`.workbuddy` 副本逐文件 sha ↔ 清单 ↔
  账本 `installed_assets.digest` 三方一致；未安装 na。随 verify_ledger
  模板部署，主仓 CI / pre-commit 零新增步骤自动生效。

## 三、过程记录（踩过的坑，负向证明的一部分）

- **探针移植第一版判 bound 只有 20（应为 29）**：`resolve_relative` 对
  `__init__.py` 里的相对导入多剥了一层，`from .x import y` 解析到
  `projects.<x>.src.x` 而不是真实包路径。修复后与探针逐能力一致
  （bound 29 / via1 3 / unbound 10），并把「相对导入再导出」钉进测试。
- **advisory 测试第一版用 `cap.get("code")` 取编码**：registry 原始 caps
  没有 code（由 codec 在 build 时分配），改走 `codec_cap_code`。
- **账本绑定用例在单测必红、手工全绿**：折腾许久后确认是自己测试里的
  `row["detail"]` 是字符串不是列表（`any(x in e for e in detail)` 迭代了
  字符）。修断言即绿——不是校验器的 bug。
- **本体投影 / FILE_LAYOUT / SCENARIO_MATRIX / TEST_MODULES 派生文件过期**：
  scripts 摘要变化导致 `check` 报「与权威源不一致」，全部用 `--apply`/
  `--emit-md` 重建，复验可复算。

## 四、复验清单

- 方法仓全量测试 315/315（0 fail / 0 error）；
- `bash scripts/check.sh` EXIT=0，acceptance 目标版本 2.1.2；
- 主仓（真实数据）advisory：`[BIND] bound 29 / via1 3 / unbound 10 /
  no_impl 1 / no_tests 4`，与独立探针一致；
- 主仓 `route_expert --check-assets`：`ok=True digest=924ab50… match=True`。

## 五、边界（不掩盖）

- **advisory 判得对还没被完整人审**：10 个 unbound 需逐条核对后修映射
  （机械推荐报告另行生成供人审），修完才谈硬门禁；
- 绑定是**必要条件不是充分条件**：有调用关系 ≠ 测的是该能力语义；
- via1 只追一跳；`import *` 不解析（记 failure，不猜）；
- 不变量 26 只查清单登记路径，清单外残留（旧版本文件）由方法仓侧
  `asset_bundle verify` 才能发现；
- 4 个 no_tests、6 个跑不绿的声明文件边界与 v2.1.0 相同，未变。

## 六、下一版候选（需另行批准）

1. **映射修正**：按 `--binding-report` 人审 diff，修 10 个 unbound 的
   tests/impl 配对（registry 数据迁移，需人批准）；
2. **硬门禁**：映射修完、advisory 被证明判得对之后，把 unbound 从告警
   升级为 tier 降级（declared）或验证失败；
3. **owner 落地**：为 open 工作项经 route_expert 输出填 owner，让
   专家路由第一次留下真实分工记录。
