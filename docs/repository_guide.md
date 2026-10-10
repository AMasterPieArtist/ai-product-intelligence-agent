# 仓库导引与整理说明

## 三条阅读路线

- **产品视角：**[项目首页](../README.md) → [产品设计](product_design.md) → [场景建议](reports/scenario_recommendations.md) → [真实案例](cases/followup_regression.md)。
- **工程视角：**[架构](architecture.md) → `evaluator/runner.py` → `evaluator/engine.py` → `evaluator/adapters.py` → [新增 Adapter](adapter_guide.md)。
- **评测视角：**[协议](evaluation_protocol.md) → `benchmarks/tasks.json` / `benchmarks/gold_review.json` → [矩阵](reports/comparison_matrix.md) → [复核索引说明](evidence/README.md)。

## 按用途命名

| 原路径 | 当前路径 | 用途 |
|---|---|---|
| `day7_dataset/` | `evaluator/` | 维护中的网页评测实现 |
| `day7_dataset/day4_runtime.py` | `evaluator/browser_runtime.py` | 浏览器状态与受控动作执行 |
| `expanded_validation/` | `benchmarks/` | 任务、材料、计划与全量报告 |
| `09_expanded_validation.ipynb` | `notebooks/evaluate_apps.ipynb` | 业务评测 |
| `08_review_and_rerun_advanced.ipynb` | `notebooks/review_and_rerun.ipynb` | 通用复核与重测 |
| `10_human_comparison.ipynb` | `notebooks/human_comparison.ipynb` | 人工对照 |
| `day7_dataset/07_public_dataset.ipynb` | `notebooks/public_dataset_validation.ipynb` | 公开语料验证 |
| `notebooks/browser_probe.py` | `tools/inspect_page.py` | 网页检查与手动操作 |
| `docs/EXPANDED_MATRIX.*` | `docs/reports/comparison_matrix.*` | 全量对比矩阵 |
| `docs/SCENARIO_RECOMMENDATIONS.*` | `docs/reports/scenario_recommendations.*` | 场景适配建议 |

代码导入、Notebook 工作目录定位、测试路径及文档链接同步更新。历史实验 ID 和记录格式版本仍保留原值，便于追溯；它们不是当前目录名。

## 不进入公开包的内容

- `baseline_code/`、`evaluation_runner_unified/` 及嵌套 ZIP：历史快照或已经应用的更新包。
- `day4/`、`day5_auto/`、`day6_business/`：早期实现副本；当前使用统一的 `evaluator/`。旧版本测试不再重复统计。
- `project_portfolio_docs/`：重复的旧 README 和求职介绍；公开入口统一到根 README 与 `docs/`。
- 早期研究、API 和浏览器实验 Notebook、空的 `src/` 占位模块及硬编码单轮脚本：不作为当前可运行入口分发。网页检查工具单独保留。
- 全量 `evaluation/`、原始公开语料、批量截图、Notebook 输出、个人应用地址和本机路径：留在原项目备份；公开包保留成果快照、复核索引和一个完整对话案例节选。

原始上传包保留在本地原件中。本整理仅创建精简后的发布工作副本，未在原始实验中修改回答、标签或计数。公开索引与案例 JSON 的内容保持原样。

## 结果与代码的关系

`docs/reports/` 对应历史 `expanded_v7`。代码重命名不意味着重新执行该实验，也不产生新的产品通过率。未来实验写入本地 `evaluation/`，采用新的 campaign 名称。

[上传 GitHub](publishing.md) · [运行指南](getting_started.md) · [离线验证](validation.md)
