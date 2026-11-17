# 发布前自检清单

发布到 GitHub 前逐项勾选。已在本地验证通过的标注 ✓。

## 功能完整性

- [x] 生成器可从 registry 读取项目定义，路径参数化（--root/--registry/--ledger/--board）
- [x] 完成度由证据逐级判定 L0-L5，禁止手填，可回落
- [x] 嵌套组件树从真实目录生成，深度/规模可控
- [x] 文档索引分 8 类 + 关联决策，路径存在性校验
- [x] 看板九视图可渲染，内嵌数据由生成器同步
- [x] 循环协议写入 capability_model
- [x] 可信性校验器：21 条不变量（含证据分层），支持 --json / --strict
- [x] 证据分层：declared/verified，run_tests.py 产出实测报告，生成器 --test-report 判定升级
- [x] 看板显示 tier 徽章与 verified 覆盖率；任务卡携带 tier 与 needs_runtime_verification
- [x] SELECT 任务队列：生成器产出 next_queue，dry-run 可见，任务卡携带已确认经验
- [x] 历史层：状态指纹驱动 append-only 事件，重跑幂等，支持状态快照回放
- [x] 经验层：自动识别候选 + 人工确认 + 任务卡消费，看板两视图可见可点
- [x] 一键初始化脚本可用（含校验器），支持 greenfield / adopt 双模式与 provenance 记录
- [x] 七种专家角色（路由 / 新建 / 考古 / 账本治理 / 审计 / 执行 / 生命周期），各含权限矩阵与停止条件
- [x] 十一个技能（route/discover/bootstrap/scan/verify/decide/lesson/guard/doc-rebuild/graph-compare/scenario-guard），标准 SKILL.md frontmatter
- [x] 技能脚本：重复立项、缺行动经验、无理由驳回均由代码拒绝
- [x] 112 个 unittest 用例（含 7 个证据分层、23 个多专家、19 个可追溯性、33 个场景与生命周期专项），零第三方依赖，临时目录隔离
- [x] CI（Python 3.10-3.13 矩阵）/ CD（tag 触发，先门禁后打包）
- [x] 示例项目已跑通，产出真实账本与看板

## 验证记录（2026-11-17）

- [x] 示例：verify_ledger 21/21 通过，--strict 退出码 0
- [x] 证据分层：无报告全 declared；带通过报告 3 个 verified（覆盖 75%）；失败报告不升级
- [x] 负向测试：verified 无依据/非法取值/越级 → 3 类 FAIL 均被校验器抓到
- [x] 负向测试：注入重复编码/手改完成度/失效路径 → 3 FAIL；篡改历史指纹/清空经验行动 → 2 FAIL
- [x] 幂等测试：连续重跑三次，事件数/指纹/候选 id/任务卡完全一致
- [x] 示例：3 条历史（genesis + 等级跃迁 + 决策演进），2 个经验候选，1 条已确认经验
- [x] 示例：next_queue 产出 1 条任务并携带已确认经验 L-001
- [x] 示例：4 能力点编码唯一；分布 L5×3 / L2×1；完成度 0.80
- [x] 示例：3 条决策，含 superseded → done 取代链，双向校验通过
- [x] 示例：文档索引 0 缺失；3 模块全部有嵌套组件树
- [x] 示例：看板 EMBED 与账本完全一致；JS 通过 node --check
- [x] 初始化脚本在临时目录跑通，4 个文件正确生成
- [x] 生成器 dry-run 与正式模式均正常
- [x] `bash scripts/check.sh` 全绿：112 测试 / 21 不变量 / 场景矩阵 / 幂等 / 同步 / 脱敏 / 文档链接
- [x] 看板 JS 通过 `node --check`；CI 用同一份门禁脚本，口径一致
- [x] 负向纪律测试：重复立项、缺 action、无理由驳回均被拒绝

## 多专家接入（0.6.0）

- [x] 路由脚本只读、确定性，账本损坏/意图冲突时 fail-closed
- [x] 存量项目盘点只写草稿与报告，不覆盖既有治理文件与源码
- [x] 新建/接入均写入 provenance，外部路径不泄露绝对路径
- [x] 接入模式生成后可通过 21 条不变量校验
- [x] docs/12-专家路由.md 与 README / AI 集成 / 落地指南互相引用一致

## 可追溯性五项反问（0.7.0）

- [x] registry + 账本可重建规范化文档三件套，默认不覆盖人工内容
- [x] 文档可抽目标/模块/编码/依赖，置信度不足时明确警告
- [x] git 真实路径可回连模块、能力编码、账本决策与历史事件
- [x] 规划图 vs 实际图五态比对，附带开发顺序、专家与前置条件
- [x] 四段式编码索引贯通文档 / 测试 / 代码 / 决策 / 事件 / 提交

## 场景矩阵与生命周期（0.8.0）

- [x] 44 个场景定义自检通过，covered 均有探针、gap 均写明代价
- [x] 覆盖矩阵为生成物，check.sh 校验与定义无漂移
- [x] 证据绑定源码摘要：改动测试源码后 verified 自动回落 declared
- [x] 并发 CAS：指纹漂移时生成器退出码 2 且不写盘
- [x] 冻结态阻止生成器、归档态阻止全部写动作、解冻需人工批准
- [x] 能力退役与任务领用状态不污染 history.events，看板 EMBED 保持同步
- [x] 生命周期状态只写账本内字段，无第二事实源

## 脱敏

- [x] 看板模板 EMBED 已替换为空账本骨架
- [x] 全项目搜索无来源项目的内部代号、数据源名与专有名词残留
- [x] 示例为虚构电商项目，无真实业务数据
- [x] 示例决策、文档、代码均为演示内容

## 文档

- [x] README（价值主张、快速开始、目录结构、视图说明）
- [x] 十四篇编号方法论文档 + STANDARD.md + 10-AI集成.md + CONTRIBUTING.md
- [x] LICENSE（MIT）
- [x] CHANGELOG
- [x] registry.example.json 含字段说明注释
- [x] 生成器 docstring 含用法说明

## 发布动作（待执行）

- [ ] 确认仓库名（建议 `ledger-driven-dev`）
- [ ] `git init` / 添加 remote
- [ ] 检查 `.gitignore`（排除 `__pycache__/`、`*.pyc`、`.venv/`）
- [ ] 提交并打 tag `v0.8.0`
- [ ] GitHub 仓库描述、README 顶图（可选）、topics 标签

## 建议的 topics

`developer-tools` `knowledge-management` `ai-agent` `documentation` `methodology` `single-source-of-truth` `python`
