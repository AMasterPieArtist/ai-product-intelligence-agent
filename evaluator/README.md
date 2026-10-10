# 网页评测核心

[运行指南](../docs/getting_started.md) · [架构](../docs/architecture.md) · [新增 Adapter](../docs/adapter_guide.md)

| 文件 | 职责 |
|---|---|
| `runner.py` | 组合计划、单批运行、记录落盘与矩阵重建 |
| `adapters.py` / `adapter_contract.py` | 页面差异适配、接口约束与完成依据 |
| `browser_runtime.py` | 观察、动作守卫、执行与截图 |
| `engine.py` | Persona 多轮流程、首答规则与报告 |
| `core.py` | 模型调用、来源线索与决策校验 |
| `stability.py` | 有限恢复与批次状态 |
| `review.py` | 复核状态校验与模板初始化 |
| `dataset_import.py` / `dataset_metrics.py` | 公共数据任务导入及指标支持 |
| `verify_dataset.py` | 可选公开语料的文件与原文一致性检查 |
| `data/` | Persona 定义、合成业务测试夹具 |
| `dataset/download_manifest.json` | 可选 DuReader 固定样本与下载校验信息 |
| `tests/` | 核心离线测试 |

从项目根目录调用 `python evaluator/runner.py --help`。实际运行建议从 Notebook 准备配置，避免手写长路径。根 `requirements.txt` 是唯一基础依赖入口。
