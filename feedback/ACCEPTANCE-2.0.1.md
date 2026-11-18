# ACCEPTANCE-2.0.1：registry schema/2 容器契约

> 性质：v2.0.0 已修好“四段码生成契约”，但没有改变 registry 的单项目容器。本契约定义下一步必须满足的容器层判据。
> 纪律：只约束方法论仓权威源；目标项目的数据迁移另经人批准、备份、重绑与独立复验，不由本文件自动授权。

## 一、四锚点

1. `registry/2`：新形状以 `schema: registry/2` + `projects[]` 表达；每个项目内部保留自己的 `modules[]` 与目录配置。
2. `dual_read`：旧形状 `project` + 平坦 `modules[]` 必须继续可读；新旧形状对同一逻辑数据必须归一化出同一组结果。
3. `stable_code`：能力 code 是稳定身份。迁移只改容器，不改、不重排、不删减 cap；单项目示例仍产出四段码。
4. `single_codec`：code 生成只能有一个权威实现；生成器、校验器与可追溯投影器必须消费同一 codec，禁止再出现裸拼五段码。

## 二、机器断言

L7 由 `scripts/acceptance.py` 追加四项检查：

| id | 判据 |
|---|---|
| `registry_schema_doc` | 本文件存在且含四锚点 |
| `registry_schema_test` | `tests/core/test_registry_schema.py` 存在且覆盖四锚点与 `normalize_projects` |
| `registry_codec_contract` | `templates/registry_codec.py` 导出 `code_namespace` / `cap_code` / `normalize_projects` / `iter_caps`；生成器、校验器、投影器均消费它；无裸拼五段码 |
| `registry_dual_read` | 旧单项目形状与新 `projects[]` 形状归一化后产生同一组 code |

## 三、红灯要求

S2 阶段必须先让 `registry_schema_test`、`registry_codec_contract`、`registry_dual_read` 失败：
旧实现没有 `registry_codec.py`，且 `scripts/trace_common.py` 仍有裸拼码路径。不得通过改验收期望值“提前转绿”。

## 四、转绿条件

只有同时满足以下条件，L7 才允许转绿：

- 权威 codec 文件被模板、目标副本和测试共同消费；
- 单项目模板、示例项目、多项目 monorepo 都通过双读；
- 目标项目数据迁移后 47 个 code 与迁移前逐项全等；
- 24 不变量、L1–L7 验收、upgrade verify、ontology check 全绿；
- 新摘要通过人批准重绑，并由干净 tag 复放核实。
