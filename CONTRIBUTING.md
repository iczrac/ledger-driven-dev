# 贡献指南

本项目的核心不是代码量，而是**纪律**。任何改动都必须保持三个性质：可复算、可验证、可追溯。

## 开发循环

```
改代码/文档 → 重跑生成器 → verify --strict → 跑门禁 → 写决策 → 提交
```

一条命令完成验证：

```bash
bash scripts/check.sh
```

它依次跑：单元测试（标准库 unittest）→ 18 条账本不变量 → 生成器幂等 → 模板/示例同步与看板 EMBED → 脱敏与文档内链。**任何阶段失败都不得提交**。本地与 CI 跑的是同一份脚本，不允许出现"本地过了 CI 挂了"。

## 改动的规则

| 你改了什么 | 必须同步做什么 |
|---|---|
| `templates/build_capability_model.py` | 复制到 `examples/demo-shop/governance/`，重跑生成器，跑门禁 |
| `templates/verify_ledger.py` | 同步示例副本；若新增检查项，补负向测试 |
| `templates/index.html.template` | 同步示例看板（用生成器重新同步 EMBED），跑 `node --check` |
| `templates/registry.example.json` | 确认 `init_project.py` 产出的骨架仍可被生成器消费 |
| `scripts/` 下脚本 | 补 `tests/` 用例；技能脚本的纪律必须被测试证明 |
| `docs/NN-*.md` | 遵守 [文档规范](docs/STANDARD.md)；更新 `README.md` 导航 |
| `experts/` / `skills/` | 更新 [AI 集成](docs/10-AI集成.md) 的能力清单 |

**只允许维护一份 `registry.json` 和一份账本**。不要新建平行报告来记录本该进账本的决策。

## 新增能力 / 决策 / 经验

- **新能力**：先改 `registry.json`，重跑生成器，确认等级符合预期；
- **新决策**：用 `ledger-decide` 或 `scripts/ledger_decide.py` 写 `proposed`；不手改 `capability_model`；
- **决策被推翻**：用 `supersedes` / `superseded_by` 建取代链，不删旧条目；
- **新经验**：用 `ledger-lesson` 确认候选，`insight` 与 `action` 缺一不可。

## 提交约定

- commit message 用动词开头：`add 经验层`、`fix 幂等误判`、`docs 补 AI 集成`；
- 一个提交只做一件事，便于回滚；
- 不要在提交里同时改生成器和账本数据，除非账本是生成器重算的必然结果。

## 发布

见 [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md)。顺序：`bash scripts/check.sh` 全绿 → 打 tag → CI 的 release workflow 产出归档。

## 零依赖承诺

运行时与测试都只用 Python 标准库。不要引入 pytest、requests 等第三方依赖——CI 环境必须开箱即跑。看板是纯 HTML/JS，不引外部 CDN。
