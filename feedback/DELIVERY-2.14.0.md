# 交付卡 · v2.14.0

**主题**：推广探路驱动的目标编排加固——能表达治理目标、能识别空转、验证门先行。

## 做了什么

1. **判据扩展**：`goal_ledger.evaluate_criteria` 支持五类 metric，新增
   `method_version`（语义版本比较，修 2.9/2.10 排序坑）与 `level_progress`
   （能力等级相对 baseline 提升）；`validate_criteria` 校验新参数，未知 metric/op
   一律 fail-closed。第 30 条不变量在账本侧同步拒绝非法判据。
2. **停滞检测**：`goal_loop.progress_fingerprint`（任务 + 相关能力等级 + 方法版本）
   + `stall_limit`（默认 2，CLI `--stall-limit`）。连续无进展即 `stagnated`、
   目标 `paused`，产出四要素结构化提议（原目标/建议变更/理由/影响），
   不再烧满预算才 `deactivated`。
3. **取证报告**：`feedback/GOAL-PROMOTE-DRYRUN.md` 记录两轮探路——
   首轮旧验证器下 3 轮空转后失活；加固后同步 v2.13 验证器复跑，验证门第 1 轮
   即抓出主仓 5 处 `unbound_verified` 脏数据并 fail-closed。

## 验证

- 目标编排单测 **29/29** 通过（新增 9 例覆盖 semver 排序、fail-closed、新判据、
  参数校验、进展指纹、停滞阈值、不变量非法判据）。
- 干净 clone 复跑：同步 v2.13 验证器 + `derived_issues.py` 后，
  `G-PROMOTE-02` 判据 = 版本达标 ∧ 能力升 L5 → 第 1 轮 `verify_failed`
  （`verified_tier_traceable`），循环正确停止，0 条待批准命令。
- 全量门禁：`scripts/check.sh` 16 阶段全绿（见发布记录）。

## 边界与下一步

- 本版**未写主仓账本**。经人批准，在干净 clone 上按可复算路径修复了
  全部 **43 处**（非报告初写的 5 处——验证器只打印前 5 个）`unbound_verified`：
  同步权威工具后用 `SymbolIndex` 符号级绑定重算（bound 29 保 verified /
  其余 14 降 declared + 派生 issue），未手工填任何状态。详见
  `GOAL-PROMOTE-DRYRUN.md` 第六节。
- 修后 clone 的 `verify_ledger --strict` 从 `26/30 + 3 na` 升为 **30/30 全绿**；
  重跑 `G-PROMOTE-02` 由第 1 轮 `verify_failed` 变为第 2 轮正确触发 `stagnated`
  （停滞检测），证明推广两道门——账本合规、循环本身——各自通过。
- 推广顺序仍为：先修账本合规 → 再跑目标循环 → 最后逐条批准网关命令回流。
  前两步已在 clone 验证；第三步**尚未执行**，主仓账本的真实修复仍须人批准。
- 主仓工作区 105 处既有改动全程未触碰；所有 dry-run 在 git archive 干净快照上进行。

## 运行方式

```bash
# 复用推广探路（干净 clone 上）
python3 scripts/goal_loop.py --target <clone> --goal-id G-001 --json
python3 scripts/goal_loop.py --target <clone> --goal-id G-001 --stall-limit 3 --emit-apply
```
