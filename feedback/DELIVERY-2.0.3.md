# DELIVERY · v2.0.3 路径全集补丁

日期：2026-11-19
性质：P2「把强制点交给机器」的收尾 —— 删掉 CI 放行名单，从根上修干净检出必红。

## 一句话结论

v2.0.2 之后主仓的 24 条不变量**只在本机成立**：干净检出必红 2 条
（`doc_paths_exist` 缺 1 个未入库测试、`component_paths_exist` 缺 10 个
被 `.gitignore` 的运行目录）。CI 当时靠一张放行名单变绿。

本版把根因修掉：生成器只从 git index 取路径全集，仓库里没有的路径进不了账本。
于是本机与干净检出产出同一份账本，放行名单删除，门禁恢复零容忍。

## 根因（不是「路径写错」，是「视角错位」）

生成器原先遍历**文件系统**，账本因此记录「这台机器上有什么」。三类噪声：

| 噪声 | 来源 | 性质 |
| --- | --- | --- |
| `<P2>/data/**`（6 条） | `.gitignore` 的运行产物 | 运行环境事实，不是仓库结构 |
| `<P2>/logs`、`<P2>/src/*.egg-info`、`<P2>/~` | 构建/临时目录，含一个误建的 `~` | 同上 |
| `<P1>/tests/unit/test_api_write_endpoint_gate_coverage.py` | 写了但从未 `git add` | 未入库证据 |

结果是最坏的一类绿灯：**它只在作者机器上成立**。别人一 clone 就是假的。

更深一层：`governance/test_report.json` 的源码绑定里还有 **4 个未入库测试文件**
（`test_akshare_listing_dates` / `test_api_write_endpoint_gate_coverage` /
`test_canonical_source_pinning` / `test_cn_bulk_raw_router`）。本机能算出摘要，
干净检出里文件根本不存在 —— 这份报告在别人机器上永远无法复现。

## 改动

### 方法仓（`ledger-driven-dev`）

1. `templates/build_capability_model.py` 新增 `RepoScope`：路径全集取自
   `git ls-files`；非 git 环境退回文件系统全集，但打印 `[WARN]` 自报未核对。
2. 五处扫描全部收窄：源码 glob、单测证据、测试记录、文档索引、组件树。
3. `norm_existing_path`：「存在但未入库」视同不存在 —— 让 registry 指向仓库外
   文件这件事在校验阶段暴露，而不是悄悄写进账本。
4. `check_freshness` 增加 `scope`：报告绑定未入库文件时返回 `untracked:<name>`，
   不再把「本机可算摘要」当成新鲜证据。
5. 新增 `tests/core/test_path_scope.py`（7 条负向证明）。
6. `docs/08-可信性校验.md` 新增「路径全集：账本只描述仓库」。
7. `METHOD_VERSION` → 2.0.3；CHANGELOG / RELEASE_CHECKLIST / `docs/23` 版本序列同步。

### 主仓（目标项目，下文脱敏记作 `<P>`）

8. `scripts/ci_governance_gate.py` 删除 `LOCAL_ONLY` 放行名单，恢复零容忍；
   docstring 记录「放行名单为什么是错的」。
9. `.github/workflows/governance.yml` 注释同步（缺口 → 已根治）。
10. 账本重算：移除 11 条仓库外路径，0 条新增；4 个未入库测试文件入库，
    使 test_report 的绑定在干净检出中可复现。
11. 重绑 v2.0.3：`M4-method-version` + `M5-method-assets`，备份
    `20261119T030418Z-dc25118a`。

## 负向证明（不是「跑通了」，是「抓得住」）

| 断言 | 证明方式 | 结果 |
| --- | --- | --- |
| 未入库文件不可见 | 造 `test_scratch.py` 未 add，断言不在 `glob_files` / 组件树 | PASS |
| 运行产物目录不可见 | 造 `data/`、`logs/`、`*.egg-info` 并 add 到 `.gitignore` | PASS |
| 文件确实在磁盘上 | 反证 `is_file()` 为真，排除「本来就找不到」的假通过 | PASS |
| 报告绑定未入库测试 | 摘要算得对但 `check_freshness` 返回 `untracked:` | PASS |
| 旧行为会误判 | 不传 scope 时同一份报告被判 fresh（说明守卫真实生效） | PASS |
| 非 git 环境 | 返回 `verified=False` 且 `why` 非空 | PASS |

## 复验数字

- 方法仓：`scripts/check.sh` EXIT=0；单测 297 全绿；acceptance 目标版本 **2.0.3** 全 PASS
- 主仓：24 pass / 0 fail / 0 na；`upgrade verify` 12 pass / 0 warn / complete=true
- 主仓干净检出（`git ls-files` 全量导出，无 `.git`）：
  - `ci_governance_gate.py` → `OK: 24 pass / 0 fail / 0 na（零放行）`
  - 重跑生成器 → 与已提交账本**逐字段一致**（仅 `generated_at` 不同）
- 证据：`verified` 仍 20/47，`freshness=fresh`，等级分布不变（L5=20 / L3=22 / L2=5）

## 一个新发现的副作用（不掩盖）

证据匹配的 hints 来自「registry 声明 + 账本既有证据」，因此存在**单向滞后**：

1. 文件未入库 → 被 scope 挡掉 → 从证据列表消失；
2. 之后补 `git add` → 文件可见了，但账本里已经没有了它的文件名；
3. hints 随之缩水 → 它不会自动回到证据列表。

本轮实测：`<P1>/tests/unit/test_api_write_endpoint_gate_coverage.py` 已入库，
但未自动回到 `<P1>.PLATFORM.PLATFORM.01` 的
unit_test 证据里。等级与 verified 计数未受影响（20/47 不变），但这是一条需要
记在案的行为：**要恢复必须在 registry 显式声明 hints，不能靠生成器猜。**

根治方向（P3）：证据匹配不应以账本自身为 hint 源形成闭环，应改为
「registry/命名约定声明 → 账本记录」的单向派生。

## 本版边界（不掩盖）

- 只保证「账本不引用仓库外路径」，未扩大证据覆盖（verified 仍 20/47）；
- `manual` 型关闭条件仍需人主动关闭；
- 多副本同步税未处理：模板一改，主仓与示例仍需手工同步（`check.sh` 字节比对兜底）；
- 证据 hints 存在单向滞后（见上节），补入库后需 registry 显式声明才能回到证据；
- 本体投影对脚本内容敏感：改模板后必须重跑 `ontology.py build --apply`，
  否则升级链第七轴 `ontology_digest` 对不上（本版踩到两次，已记入检查清单）。
