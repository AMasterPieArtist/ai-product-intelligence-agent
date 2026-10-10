# 上传 GitHub 与展示网页

这是整理后的**完整发布项目**，不是增量补丁。先解压到一个新文件夹，检查 README 和 `docs/index.html`，不要直接混入旧的 Day 目录。

## 用现有 GitHub 仓库发布

1. 备份现有本地仓库，尤其是 `.env`、本地应用配置和 `evaluation/` 原始记录。
2. 保留原仓库的 `.git`、`.env`、`.venv` 和本地 `evaluation/`。将发布包 `ai-product-intelligence-agent/` 内的文件复制到仓库根目录，不要再套一层同名目录。
3. 仅覆盖不能删除旧文件。根据[迁移清单](repository_guide.md)，把旧 `day4/`、`day5_auto/`、`day6_business/`、`day7_dataset/`、`expanded_validation/`、`baseline_code/`、`evaluation_runner_unified/`、`project_portfolio_docs/` 及旧编号 Notebook 移至仓库外的备份目录。旧 `notebooks/` 先整体备份，再放入新版四个入口；旧 `tools/prepare_persona_check.py` 不再需要。旧 `docs/`、根目录旧介绍和 `src/` 占位代码也先移出再放入新版，避免保留两套入口。
4. 自用配置可根据旧内容填写新的 `benchmarks/app_settings.json`；不要公开提交该文件。整理改变了代码路径与指纹，新的在线实验使用新的 campaign 名称，历史数据不用重写。
5. 在新目录执行 `python tools/check_all.py` 和 `python tools/check_release.py`。离线检查不会启动应用或消耗模型 API。
6. GitHub Desktop 的 Changes 中检查新增、删除和重命名。不要提交密钥、登录状态、个人配置、Notebook 输出和全部历史实验目录。`.gitignore` 对已经跟踪的文件不自动生效，需要从跟踪中移除并保留本地备份。
7. Commit 后 Push origin。提交说明可用：`Reorganize evaluation project and add scenario report showcase`。

如不需要保留旧仓库历史，也可在 GitHub Desktop 为解压后的新目录创建仓库并发布；不要把 ZIP 文件本身当作源码目录上传。

## 让 HTML 成为可访问的网页

仓库中的 HTML 文件页用于看源码，在线交互演示需要静态托管。本项目已提供 `docs/index.html` 与相对链接：

1. 上传完成后，在仓库 **Settings → Pages** 打开发布设置。
2. Source 选择 **Deploy from a branch**。
3. Branch 选择实际提交的分支（通常为 `main`），目录选择 **`/docs`**，保存。
4. 等部署完成，使用 GitHub 显示的站点地址验证场景筛选、Persona 切换、矩阵搜索和证据链接，再把真实地址填写到仓库 About 和简历。

本次只整理文件，没有替你上传仓库或启用站点。GitHub Pages 部署以账号及仓库实际权限为准。

官方说明：[配置 GitHub Pages 发布源](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)、[创建 GitHub Pages 站点](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site)。

## 建议的展示顺序

仓库首页 → 场景适配建议 → 全量对比矩阵 → 多轮案例 → 架构与 Adapter。

保留方法和结论之间的证据关系。展示页是历史实验快照；原始运行数据仍由本地保留，不因目录整理改变评测结果。
