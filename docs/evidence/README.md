# 公开证据说明

- [expanded_reviews.json](expanded_reviews.json)：192 个完成组合的 AI 辅助复核索引，以 96 行同题 × Persona 配对组织；含任务、来源状态及证据说明。
- [followup_case.json](followup_case.json)：EV011 资料核查组合的多轮回答和复核节选，对应[案例分析](../cases/followup_regression.md)。
- [案例截图](../assets/followup_regression.png)：该组合追问后的页面截图。

JSON 中的 `record_path`、`report_path`、`original_record_path` 是历史实验中的定位标识。完整原始运行目录没有公开分发，不能把它们当作当前仓库内的可点击路径。网页报告直接嵌入复核依据，链接指向这里的公开索引。

上述 JSON 从上传项目原样保留。来源无法确定包含采集限制，AI 辅助复核不等于独立人工标注。材料原文可在 `benchmarks/materials/` 中查阅。
