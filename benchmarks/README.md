# 业务任务与评测设计

[运行指南](../docs/getting_started.md) · [任务列表](TASKS.md) · [复核标准](GOLD_REVIEW.md) · [复核协议](REVIEW_PROTOCOL.md)

- `tasks.json`、`materials/`：24 道任务与 8 份模拟资料。
- `gold_review.json`：任务级复核依据，留在评测端，不传给模拟用户或被测知识库。
- `batches.json`、`prepare.py`：组合计划、配置指纹和续跑控制。
- `app_settings.example.json`：应用配置样例，复制为 `app_settings.json` 后使用。
- `campaign_report.py`、`decision_report.py`、`summarize.py`：全量矩阵、场景规则与报告生成。
- `human_comparison.json`、`quality_comparison.json`、`compare_metrics.py`：人工对照模板与指标计算，当前有效配对为 0。
- `test_*.py`：计划、口径和场景建议规则测试。

材料与参考标准保持原样。完整网页交互任务适配在 `evaluator/`，配置和运行方法见根 README。
