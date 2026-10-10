# 运行指南

[返回项目说明](../README.md) · [仓库导引](repository_guide.md) · [查看成果](reports/scenario_recommendations.md)

## 只看成果

下载并解压完整项目，双击 `docs/index.html`。两个 HTML 报告均为离线页面，可以直接筛选、切换 Persona 和展开复核依据，不需要 API Key 或浏览器自动化环境。

## 安装环境

在 VS Code 打开整个项目文件夹。终端位置应是包含 `README.md` 和 `requirements.txt` 的根目录。

```bash
python -m venv .venv
```

Windows PowerShell 激活：`.venv\Scripts\Activate.ps1`；macOS / Linux：`source .venv/bin/activate`。已有可用环境可沿用。Notebook 选择同一 Python 解释器；若缺少内核包，执行 `python -m pip install ipykernel`。

```bash
python -m pip install -r requirements.txt
python -m playwright install chromium
python tools/check_all.py
```

离线测试不打开产品、不调用模型。公开语料相关 3 项在数据未准备时跳过。

## 配置自己的应用

1. 复制根目录 `.env.example` 为 `.env`，填写测试 Agent 的模型 API Key；这与被测应用内部模型配置相互独立。
2. 复制 `benchmarks/app_settings.example.json` 为 `benchmarks/app_settings.json`，填入自己的应用 URL、模型、检索、提示词版本等配置；无法确认的项写 `unknown`。
3. 将 `benchmarks/materials/` 中 8 份 TXT 配置到两套被测应用，索引完成并发布后，把各自 `material_confirmed` 改为 `true`。不要把评测端的 `gold_review.json` 上传到知识库。
4. Adapter 对应两个已验证页面结构。不同前端或平台版本可能需要修改定位与完成判据，见 [Adapter 指南](adapter_guide.md)。

样例 URL 是占位符，不会沿用作者的在线应用。真实配置和 `.env` 已列入忽略规则。

## 运行业务评测

打开 `notebooks/evaluate_apps.ipynb`：

1. 用新的 `CAMPAIGN`，例如 `my_evaluation_v1`；默认 `BATCH='smoke'`、`MODE='rules'`。
2. 运行初始化和准备计划单元格。此时只创建配置并检查预算，不会操作产品。
3. 准备好后设置 `RUN_TESTS=True`，运行启动格。先完成 8 个 smoke 组合并检查回答及来源采集。
4. 同一配置下依次设 `BATCH='1'` 至 `'6'`，每次重新准备计划再启动。已完成组合自动跳过，失败和未运行组合可以续跑。
5. 结果保存在 `evaluation/expanded_campaigns/<campaign>/results/<批次>/`。变更代码、材料或远端配置时使用新 campaign，避免混合实验条件。

## 复核与汇总

打开 `notebooks/review_and_rerun.ipynb`，把 `RESULT_DIR` 改为实际批次目录。生成离线工作台后，根据 [评测协议](evaluation_protocol.md)与 `benchmarks/GOLD_REVIEW.md` 填写任务和来源状态。导出 `human_reviews.json` 并放回该批次，再汇总：

```bash
python benchmarks/summarize.py evaluation/expanded_campaigns/my_evaluation_v1
```

生成 `campaign_summary.md`、`campaign_matrix.html/md/json`、`campaign_analysis.md` 和 `scenario_recommendations.html/md/json`。公开仓库内 `docs/reports/` 是历史展示快照，不会被这个本地汇总命令自动覆盖。

## 重建公开展示页

```bash
python tools/export_public_reports.py
```

此命令只读取公开复核索引，重建四份 HTML / Markdown 展示报告，不调用产品，也不改写复核结果。若要发布一轮新实验，先从本地结果制作经过检查的公开索引与案例，再更新它们；不要直接公开完整配置、登录状态或日志。

## 可选入口

- `notebooks/human_comparison.ipynb`：执行人工对照，真实计时与独立标签需另行收集，见[人工对照说明](human_evaluation.md)。
- `notebooks/public_dataset_validation.ipynb`：先运行 `python tools/prepare_public_dataset.py` 准备固定的 DuReader 子集，并阅读原数据协议。本公开包不附语料。
- `tools/inspect_page.py`：对指定 URL 做输入框、页面文本与截图检查，支持手动操作；命令见 [Adapter 指南](adapter_guide.md)。
