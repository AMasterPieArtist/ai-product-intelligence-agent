# AI Product Intelligence Agent

**面向 AI 产品经理的应用体验与场景适配评估工具。**

把业务任务与不同用户的完成标准转为可执行的网页交互，保存回答及来源证据，经复核输出场景建议、产品对比矩阵和改进线索。当前以两套自建知识库应用验证流程，新增产品通过网页 Adapter 接入。

**6 类业务场景 · 24 道模拟任务 · 4 类 Persona · 192 个完成组合**

[场景建议](docs/reports/scenario_recommendations.md) · [对比矩阵](docs/reports/comparison_matrix.md) · [结果分析](docs/reports/results_analysis.md) · [产品设计](docs/product_design.md) · [运行指南](docs/getting_started.md)

## 先看什么

| 阅读目的 | 入口 | 可以看到什么 |
|---|---|---|
| 2 分钟了解项目价值 | 本页 → [产品设计](docs/product_design.md) | 面向谁、解决什么问题、如何定义完成标准 |
| 直接查看场景适配结论 | [场景建议文字版](docs/reports/scenario_recommendations.md) | 哪类需求优先哪套配置、哪些子场景仍有缺口 |
| 体验可筛选网页 | [成果导航页文件](docs/index.html) | 场景 / Persona 切换、逐题筛选与证据展开 |
| 核查一个真实案例 | [多轮核查案例](docs/cases/followup_regression.md) | 从问题、回答、追问到复核与改进建议 |
| 看实现与扩展方式 | [架构](docs/architecture.md) → [Adapter 接入](docs/adapter_guide.md) | 页面执行、Persona 决策、证据和报告如何协作 |

GitHub 文件页通常展示 HTML 源码。下载项目后双击 `docs/index.html` 即可离线体验；也可按[发布说明](docs/publishing.md)将 `docs/` 发布为 GitHub Pages，再把真实演示地址放到仓库 About / 简历。所有演示页均不调用 API。

## 要辅助什么决策

产品经理比较 AI 应用时，不仅需要知道“答得对不对”，还要判断“谁能完成什么任务、哪里需要补问、结论依据能否追溯”。本项目把这一过程组织为：

**业务任务 → 网页执行 → 按需追问 → 证据留存 → 分层复核 → 场景建议 → 指定组合回归。**

| 用户需求 | 行为设计 | 对应决策问题 |
|---|---|---|
| 快速查询 | 阅读首答，关注事实与必要条件 | 简单任务能否直接完成？ |
| 资料核查 | 来源不足或归属不明时追问 | 能否追溯到支持结论的文档与片段？ |
| 新员工理解 | 需要时请求解释术语或下一步 | 回答是否足以支持操作？ |
| 谨慎审核 | 检查版本、日期和约束 | 是否遗漏会改变决策的条件？ |

初始问题一致，Persona 改变追问和验收标准；每个组合最多一次追问。执行结束、任务通过和来源核验分开记录，避免把“页面有回复”当作“业务成功”。

## 已实现的能力

- **可扩展的网页接入：**Dify / Coze 两个已验证 Adapter，共用任务、行为和复核流程；网页检查工具支持指定 URL 与手动操作，完整评测仍需适配页面。
- **受控执行：**动作校验、追问上限、有限重试、异常留档、按未完成组合续跑。
- **证据与复核：**保留当前轮回答、可见来源、截图和决策记录；离线工作台支持填写复核结果、定位原文与准备重测。
- **直接支持场景判断：**六类场景建议与 96 行配对矩阵，支持从建议下钻到任务及复核依据；共同失败与证据不足有单独提示。

## 验证范围

扩展轮 `expanded_v7`：24 题 × 4 类 Persona × 2 套应用，192 个唯一组合完成，201 次尝试、9 次执行异常。全部完成组合有 AI 辅助证据复核。比较结果与口径完整保留在[结果分析](docs/reports/results_analysis.md)和[复核索引](docs/evidence/expanded_reviews.json)中。

这是两套具体配置下的模拟业务验证，不是平台通用排名或真实用户研究。人工对照尚未完成，暂不报告效率或准确性提升。来源无法确定可能由采集不足造成，详见[已知限制](docs/known_limitations.md)。

## 本地使用

仅看展示：双击 `docs/index.html`，无需安装依赖。

运行评测：Python 3.12，先安装依赖并完成应用配置，步骤见[运行指南](docs/getting_started.md)。

```bash
python -m pip install -r requirements.txt
python tools/check_all.py
python tools/check_release.py
```

公开版离线测试：87 项发现，84 项执行通过，3 项因未分发 DuReader 原始语料而跳过。结构整理移除了旧实现的重复测试目录；计数不与历史 117 项直接比较。未重新调用被测产品。

## 代码入口

| 目录 / 文件 | 职责 |
|---|---|
| `evaluator/` | 页面 Adapter、浏览器执行、Persona 决策、记录与单批报告 |
| `benchmarks/` | 24 道任务、8 份模拟材料、批次计划、复核标准与全量报告 |
| `notebooks/evaluate_apps.ipynb` | 准备并运行业务评测，生成场景建议 |
| `notebooks/review_and_rerun.ipynb` | 已有记录复核、用量统计与指定组合重测 |
| `notebooks/human_comparison.ipynb` | 待完成的人工对照实验 |
| `notebooks/public_dataset_validation.ipynb` | 可选的公开语料流程验证 |
| `tools/` | 页面检查、复核、离线验证与公开报告导出 |
| `docs/` | 产品设计、技术说明、网页成果和精选证据 |

完整文件迁移说明见[仓库导引](docs/repository_guide.md)。本地配置、密钥、运行原始数据不放入公开仓库；公开证据为索引与精选案例，非全部原始截图。参考来源及数据使用说明见 [NOTICE.md](NOTICE.md)。
