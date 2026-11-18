# S1：registry schema v2 只读基线与风险清单

> 性质：用户选择“registry schema v2”后的第一阶段。**只读**，不改方法仓权威源，不改目标项目账本/看板/报告。
> 目标项目记作 `P`；真实项目名在本文件中脱敏为 `P-A` / `P-B` / `P-C` / `P-D`。
> 本文件只固化事实与风险，不构成对写盘迁移的新授权。

## 一、结论摘要

当前系统处于稳定的 v2.0.0 终态：

- 方法仓 `main` 在 `5589363`，tag `v2.0.0` 的发布提交为 `58b1149`；工作树干净；
- 主仓 `governance/registry.json` 仍是 **单项目容器**：顶层 `project` + 平坦 `modules[]`；
- 主仓账本仍是 **1 个项目 / 20 模块 / 47 能力**，47 个 code 全为四段；
- 24 不变量、14 项 L1–L6 验收、12 项升级复验、本体一致性检查全部通过；
- 因此本次升级不是“修红”，而是把已经用编码契约绕开的**容器层不一致**显性化、schema 化。

一句话风险判断：最大危险不是把 `project` 改成 `projects[]`，而是改变能力 code 或减少/重排能力序列；那会同时打断 history 指纹、work_items scope、证据绑定与看板 EMBED。最小迁移路径必须**冻结 code 作为身份**，只改容器结构。

## 二、只读基线

### 2.1 仓库边界

| 对象 | 位置 | 状态 |
|---|---|---|
| 方法论权威源 | `ledger-driven-dev` | 独立 git 仓；`main=5589363`；tag `v2.0.0` 已发布；工作树干净 |
| 目标项目 `P` | `P` 根仓库 | 存在大量既有未提交文件；本阶段不触碰无关字节 |
| 权威账本 | `P/governance/DECISION_LEDGER.json` | 只读 |
| 能力注册表 | `P/governance/registry.json` | 只读 |
| 看板 | `P/governance/index.html` | 只读 |
| 测试报告 | `P/governance/test_report.json` | 只读 |

### 2.2 权威文件摘要

| 文件 | sha256 |
|---|---|
| `governance/registry.json` | `fef26fdf82f784c5f12e11f3544d0d8ffd10ded9689933aa62bf1eda1f103d32` |
| `governance/DECISION_LEDGER.json` | `04ebc4a039c41ae25eddc73cf8a65216205ead5a61a6462b8529a524df26124d` |
| `governance/index.html` | `17101d406a94f74cce309dcd87b82f768e9f3d601787c3b2ebfb7e5c69185d4b` |
| `governance/test_report.json` | `eac667e2366d3ba22bb9ecd3f4790aaf4c81c47e0db38b46013085144dc77c83` |

### 2.3 账本状态

| 维度 | 当前值 |
|---|---|
| `method_version` | `2.0.0` |
| `method_assets.digest` | `99856a1d9c346d0acfa8390eb1ef1cb1b78293375e57b1d82d3677b82edf41df` |
| `installed_assets.digest` | `95e1e5ca4aa519abbb6ffa28538f821b63f863963e8d907108a7b8614ca5d69f` |
| `ontology_digest` | `af5527160ddc879735e5dcc23f23ee39dbccc9fe98deb935211c9725fd7d9904` |
| `board_skeleton.digest` | `735bcd09fb54fd1a174ad6d786aa72b4b0c23d24dcf80b40a46a22f33c6c84fe` |
| capability_model | 1 project / 20 modules / 47 capabilities |
| code 段数 | 47 个四段码，0 个五段码 |
| level 分布 | `L5:20 / L3:22 / L2:5` |
| evidence_tier 分布 | `verified:20 / declared:27` |
| `test_results` | 182 用例，绑定真实报告 |
| `activation.state` | `active`，`all_active=true` |
| `history.current_fingerprint` | `559a1a6355075c64…` |

### 2.4 当前门禁结果

| 检查 | 结果 |
|---|---|
| `governance/verify_ledger.py --strict` | `24/24` PASS |
| `scripts/acceptance.py --check --json` | `overall=pass`，14 项 checks 全 PASS |
| `scripts/upgrade.py --target P verify --json` | `overall=pass`，12 pass / 0 warn / 0 fail |
| `scripts/ontology.py check --target P --json` | `ok=true`，`drift_count=0`，31 条公理 |

## 三、当前 registry 的真实形状

顶层键：

```text
_comment
project
_field_guide
modules
comment
```

`project` 是单个对象，字段包括 `code` / `name` / `root` / `governance_gate` / `contracts_dir` / `unit_test_dir` / `test_record_dir` / `docs_dir` / `governance_dir`。

`modules[]` 是平坦数组，20 项；每个模块含 `code` / `name` / `src[]` / `caps[]`。
四项逻辑项目不是容器，而是**内嵌在模块 code 前缀里**；脱敏后形如 `<P-A>.DATA`、`<P-B>.PROC`、`<P-C>.KNW`、`<P-D>.API`。

`caps[].code` 在当前生成器中不是权威字段：生成器实际用

```python
cap_ns = code_namespace(project_code, module_code)
cap_code = f"{cap_ns}.{domain}.{cidx:02d}"
```

也就是说，cap 在 `caps[]` 中的**顺序**决定末尾序号。registry 手写的 `code` 只用于既有证据提示。这是本次迁移必须冻结顺序的直接原因。

## 四、消费者地图

### 4.1 直接消费 registry 的核心路径

| 路径 | 作用 |
|---|---|
| `templates/build_capability_model.py` / `governance/build_capability_model.py` | 生成 capability_model、architecture、board EMBED |
| `templates/verify_ledger.py` / `governance/verify_ledger.py` | 不变量 #9 `registry_impls_exist` 直接读 registry |
| `scripts/trace_common.py` | `iter_caps()` 为 compare/code_index/rebuild_docs/trace_git 等提供能力展开 |
| `scripts/ontology.py` | A4 基数公理、Capability 实体来源、目标项目漂移检查 |
| `scripts/acceptance.py` | L6 检查生成器编码契约；刻意不读目标项目 registry 数据 |
| `scripts/upgrade.py` | 三工具同步、摘要重绑、版本 verify |
| `scripts/scenario_guard.py` / `scripts/agent_gateway.py` / `scripts/route_expert.py` | 写前预检、registry CAS、专家路由 |
| `scripts/scale_budget.py` / `scripts/file_layout.py` / `scripts/discover_project.py` / `scripts/init_project.py` | 规模预算、布局契约、发现与初始化 |

### 4.2 摘要与绑定

registry 变化会影响：

- `registry_sha` 与 `agent_gateway.registry_cas`；
- `evidence_binding.inputs` / `source_digest`；
- `test_results.source_sha256`；
- `capability_model.history.current_fingerprint` 与 CAS；
- 看板 EMBED；
- `method_assets.digest` / `installed_assets.digest` / `ontology_digest` / `board_skeleton` 中的至少前三项；
- 观察包导出的 registry 字节摘要。

## 五、风险清单

1. **容器双读缺口**：生成器、校验器、投影脚本都假设 `project` + `modules[]`。schema v2 若不双读，单项目模板/demo 会立即失效。
2. **第二套 codec**：`scripts/trace_common.py:70` 仍裸拼 `{code}.{mcode}.{domain}.{idx:02d}`。对主仓会得到五段码，与账本脱钩；L6 当前只覆盖生成器，没有覆盖这里。
3. **code 身份脆弱**：code 由 `caps[]` 顺序生成，不是显式权威字段；重排、插入、删除能力都会改 code。
4. **history 连锁**：history 状态以 code 为键。任何 code 变化会让链连贯、指纹自证、状态编码、末事件一致性四项同时失败。
5. **work_items 与 refs 连锁**：scope/refs 的合法集合从 codes 派生，code 变化会形成死链；上一轮 P1 预演已实证 3 个 FAIL。
6. **证据绑定连锁**：`impl` / `hints` 的相对基准若随 `project.root` 改变，verified 会回落 declared；不得为了让门禁变绿重造报告。
7. **ontology 假一致**：当前 `ontology check ok=true` 是因为账本也维持 1 个项目，并非 registry 真实表达多项目。schema v2 后应变成真正一致。
8. **摘要连锁**：改模板、docs、示例 registry、本体源文件或三工具副本，都需要 M5/M7 重绑；否则 `upgrade verify` 必红。
9. **工具副本同步**：`check.sh` 强制 `governance/`、模板、demo 副本字节一致；只改模板不复制会失败。
10. **版本与计数漂移**：acceptance 的 `literal_drift` 会扫 docs/CHANGELOG/RELEASE_CHECKLIST/脚本中的版本与计数陈述。

## 六、候选 schema v2 契约

仅作为 S2 红灯定义输入，尚未生效：

```json
{
  "schema": "registry/2",
  "projects": [
    {
      "code": "<P1>",
      "name": "项目一",
      "root": "projects/<p1>",
      "governance_gate": true,
      "contracts_dir": "src/contracts",
      "unit_test_dir": "tests",
      "test_record_dir": "docs/test_records",
      "docs_dir": "docs",
      "governance_dir": "governance",
      "modules": [
        {
          "code": "<M>",
          "name": "模块",
          "src": ["projects/<p1>/src/..."],
          "caps": [
            {
              "name": "能力",
              "domain": "<DOMAIN>",
              "code": "<P1>.<M>.<DOMAIN>.01",
              "impl": ["projects/<p1>/src/..."],
              "hints": ["<P1>.<M>.<DOMAIN>.01"]
            }
          ]
        }
      ]
    }
  ]
}
```

兼容要求：

- 新版必须读 `schema=registry/2` + `projects[]`；
- 旧版单项目 `project` + `modules[]` 必须继续可读，至少覆盖模板与 demo；
- 两种形状对同一逻辑数据必须产出同一组四段码；
- `cap.code` 在新形状中应升级为稳定身份候选，但第一阶段先冻结顺序并核对与旧码全等；
- `code_namespace()` 应成为唯一 codec，供生成器与 `trace_common.iter_caps()` 共用。

## 七、最小可复放迁移顺序

1. **S2 红灯**：新增 registry schema v2 契约文档与测试；在旧实现上应失败，尤其覆盖 `projects[]` 双读与 `trace_common` 五段码。
2. **S3 转绿**：改权威源；先统一 codec，再做容器双读；同步主仓三工具与 demo 副本；重算派生文档与本体投影。
3. **S4 人批准数据迁移**：显式批准、带清单备份、append-only 审计；把目标项目 registry 改为四项目 `projects[]`，保持 47 个 code 与顺序不变。
4. **S4 复验**：生成器 dry-run 确认 `no_regress=[]`；重跑 24 不变量、acceptance、upgrade verify、ontology check、check.sh。
5. **发版与独立复放**：新 tag 干净树复算摘要，并与目标项目账本比对；不通过则回滚，不留半绿。

## 八、本阶段边界

本文件写入后仍不改变任何权威字节。未做：

- 未修改 `governance/registry.json`；
- 未修改账本、看板、测试报告；
- 未改方法仓模板、脚本、文档与测试；
- 未升版本、未打 tag；
- 未执行任何 `--apply` 数据迁移。

下一步应在用户继续授权下进入 S2：定义红灯契约与测试。
