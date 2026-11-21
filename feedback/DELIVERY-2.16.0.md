# 交付卡 · v2.16.0

**主题**：投影新鲜度不变量——让健康度明细不能再落后于测试证据。

## 做了什么

1. 新增第 31 条账本不变量 `analytics_test_results_detail_valid`：从
   `test_results.cases` 实算 pass/total，核对 `summary` 与健康维度
   `test_pass_rate.detail`。不一致即 fail-closed。
2. 修正 v2.15.0 遗留的投影陈旧：测试报告已是 437/437，账本健康明细仍是
   418/418；本版按当前证据重算为 438/438（新增 1 个负向测试）。
3. 第 31 条归入已有分析层能力 `METHOD.GOV.ANALYTICS.14`；新增文档
   `docs/35-投影新鲜度不变量.md`；验证器三份副本逐字节同步。

## 验证

- 新增负向用例：手改 `detail` 后必须由 #31 抓到。
- `verify --strict`：31 条检查无 fail（1 条目标编排为 na）。
- 全量测试 438/438、`test_modules`、ontology、`check.sh` 16 阶段均按权威门禁复跑。
- 账本健康明细已由 418/418 重算为 438/438；health 94.3，派生 issue 2 条保持 open。

## 边界

- 本版只修方法仓自身投影，不改目标项目账本与业务文件。
- 目标项目接入运行时信号仍需单独的人批准流程。
