# 来源与使用说明

- 项目早期研究原型参考 Deep Research from Scratch 教程的 scoping 结构；这些探索 Notebook 不在当前精简发布包中。当前网页执行流程为 Python、asyncio、Playwright 与模型 API。
- Persona 行为与体验评审思路参考 [d-wwei/product-review](https://github.com/d-wwei/product-review)。本项目没有直接引入其第三方执行模块，不将该项目的规模或效果视为自身成果。
- DuReader-robust 官方来源：[Baidu DuReader-Robust](https://github.com/baidu/DuReader/tree/master/DuReader-Robust)。固定数据包 SHA256 和 5 个样本 ID 见 `evaluator/dataset/download_manifest.json`。数据用途受原 Participant Agreement 约束，使用前须阅读；原始语料、参考答案及大体积数据包不随此公开包分发。下载准备由用户主动运行脚本。
- `benchmarks/materials/` 及业务任务为原创模拟场景；Persona 是行为模拟，不是客户访谈或真实用户反馈。
- 展示报告保留原实验结果及 AI 辅助复核署名。未测量真实商业收益、人工时间节省或相对人工准确性提升。
- 未替用户或第三方重新指定开源许可证；如需对外授权复用代码，请仓库所有者另行选定适用许可证。
