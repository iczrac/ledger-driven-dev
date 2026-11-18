# v2.0.1 发版报告：registry schema/2 容器版

> 发版序列：S1 基线 → S2 红灯 → S3 转绿 → S4 人批准重绑 → 发版 → 独立复放核实。
> 目标项目记作 `P`；本版不实现语义图 R4，也不改任何业务源码。

## 一、发版结论

v2.0.1 把 v2.0.0 只修到“编码契约”的 registry/2 推进到完整容器契约：
`schema=registry/2` + `projects[]` 成为合法输入，旧 `project` + `modules[]` 继续双读；
生成器、校验器、可追溯投影器共享一个 codec；目标项目的 registry 已按此形状迁移并逐 cap 保持码不变。

目标项目终态：

- `method_version=2.0.1`；
- registry 4 个项目 / 20 模块 / 47 能力；
- capability_model 同样 4 个项目 / 20 模块 / 47 能力；
- 47 个 code 全四段，迁移前后逐项全等；
- level `L5:20 / L3:22 / L2:5`，无降级；
- tier `verified:20 / declared:27`，182 用例真实报告绑定，`activation=active`；
- 24 不变量全 pass；acceptance L1–L7 共 18 项全 pass；upgrade verify 12 pass。

## 二、发版内容

- `templates/registry_codec.py`：唯一 codec，提供
  `code_namespace` / `cap_code` / `normalize_projects` / `iter_caps`；
- `build_capability_model.py`：遍历归一化项目列表，`summary.projects` 动态化；
- `verify_ledger.py`：不变量 #9 改由 codec 展开，支持 v1/v2 双读；
- `trace_common.py`：删除裸拼五段码，消费同一 codec；
- 第四工具副本 `governance/registry_codec.py` 纳入 TOOLING / 布局 / 初始化 / 同步门禁；
- `acceptance/1` L7 四项：`registry_schema_doc` / `registry_schema_test` /
  `registry_codec_contract` / `registry_dual_read`；
- 文档：`ACCEPTANCE-2.0.1.md`、S1/S2/S3/S4 证据、CHANGELOG、顺延表、派生布局与测试地图。

## 三、关键证据链

| 阶段 | 文档 | 结论 |
|---|---|---|
| S1 | `feedback/S1-REGISTRY-SCHEMA-V2-BASELINE.md` | v2.0.0 基线全绿；风险集中在容器双读与第二套 codec |
| S2 | `feedback/S2-2.0.1-RED.md` | L7 两项 fail、专项 7 项全未通过 |
| S3 | `feedback/S3-2.0.1-GREEN.md` | L7 四项 pass、282/282 单测、本体摘要重算 |
| S4 | `feedback/S4-2.0.1-REBIND.md` | 备份、迁移、CAS 重算、M4/M5/M7 重绑、24 不变量全 pass |

## 四、目标项目变更与回滚

- 迁移前独立备份：`20261118T184526Z-schema-v2-pre`；
- `upgrade.py apply` 自带备份：`20261118T184649Z-14cf9420`；
- 批准人：`用户选择-registry-schema-v2-S4`；
- 升级审计：`governance_meta.upgrade_log` append-only 增至 13 条；
- 历史 append-only：新增 `seq=3` change 事件，指纹 `559a1a63… → 624dd71f…`；
- 回滚可用 `upgrade.py rollback --backup-id <id> --approved-by <人>`，但会丢失本次容器迁移，需重做 S4。

## 五、摘要

| 摘要 | 值 |
|---|---|
| `method_assets.digest` | `b021d49f36d2eb7a2fd61a4cff4b683f696e210f3bb6412ee0690875c4536834` |
| `installed_assets.digest` | `924ab50312ea6999ba3725d5e5be6711b6e6798d90268ea528ea254d345c944c` |
| `ontology_digest` | `b15889efe5cb2c4b95c4973503df1e4b6a5af5603be1fd670ef0e469c914699a` |

## 六、边界与未做

- 语义图 R4（Statement 再化 / K3 推理机 / 最小割集 RCA）未实现；
- `scale_budget` 告警与 6 条 open 观察按既有状态保留；
- 目标项目根仓库有大量既有未提交文件，本版只改其治理文件，不代替用户提交整个主仓；
- 独立交付复放核实另见 `feedback/DELIVERY-VERIFY-2.0.1.md`。
