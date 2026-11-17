---
name: ledger-guard
description: |
  统一质量门禁：一条命令跑完单元测试、21 条账本不变量、生成器幂等、看板 EMBED 一致、
  模板与示例同步、脱敏扫描。提交前、CI、发布前都用它，不允许只跑其中一部分。
  Triggers: "提交前检查", "全量验证", "CI", "发布前检查", "check",
  "测试都过了吗", "门禁", "guard", "quality gate"
license: MIT
metadata:
  author: ledger-driven-dev
  version: "0.9.0"
  risk_level: read_only
  related_skills: [ledger-scan, ledger-verify, ledger-decide, ledger-lesson]
---

# Ledger Guard

把"我以为没问题"变成"一条命令证明没问题"。本地、CI、发布前跑的是**同一份脚本**，不存在"本地过了 CI 挂了"的口径差异。

## When to Use

任何提交前；CI 的每个 push / PR；打 tag 发布前。

## 输入 / 输出契约

| 项 | 值 |
|---|---|
| 输入 | 项目根目录（脚本自动定位） |
| 输出 | 各阶段 PASS/FAIL 汇总；失败返回非零退出码 |
| 副作用 | 无写账本；幂等检查在临时目录进行 |

## 步骤

```bash
# 唯一入口（本地 / CI 通用）
bash scripts/check.sh

# 等价的显式分解（排错时用）
python3 -m unittest discover -s tests -v          # 1. 单元与集成测试
python3 governance/verify_ledger.py --root . --strict   # 2. 21 条不变量
bash scripts/check.sh --only-idempotence           # 3. 连续重跑幂等
```

## 检查项

1. **测试**：`unittest discover`，覆盖等级判定、指纹、历史链、校验器负向、技能纪律；
2. **账本**：`verify --strict`，18/18；
3. **幂等**：连续重跑生成器，事件数 / 指纹 / 候选 id / 任务卡必须完全一致；
4. **同步**：看板 EMBED 与账本一致；模板脚本与示例副本一致；
5. **脱敏**：无来源项目内部代号与专有名词残留；
6. **文档**：Markdown 内链全部指向存在的文件。

## 禁止

- 跳过失败项"先提交再说"；
- 只跑 `verify` 就宣称全量检查通过；
- 在 CI 里用与本脚本不同的命令集合（口径必须一致）。

## 失败处理

按失败阶段定位：测试失败看 `tests/`；账本失败交 `ledger-verify` 修复表；幂等失败说明生成器有状态漂移，修生成器本身而非调整账本。
