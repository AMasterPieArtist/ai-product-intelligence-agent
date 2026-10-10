# 发布版验证

本次只整理结构、更新导引与展示入口，没有重新运行在线产品评测。

- `python tools/check_all.py`：87 项发现，84 项执行通过，3 项因未附 DuReader 原始语料而跳过。旧实现重复测试移出后，不直接沿用历史 117 项计数。
- `python tools/check_release.py`：检查 Python 与 Notebook 代码语法、Notebook 输出清理、本地文档链接、公开索引统计和矩阵行数。
- 原始公开复核索引、案例 JSON、24 道业务题、参考标准与 8 份模拟材料与上传包逐字节核对。
- `node tools/check_report_ui.cjs`（可选，需 Node.js）：HTML 的矩阵筛选、场景切换与 Persona 切换执行脚本检查；静态入口与案例使用相对链接，不依赖外部服务。
- 未在真实浏览器中完成视觉验收，也未验证 Windows 本地新环境、远端页面或 GitHub Pages 的部署状态。上传后先打开成果入口检查。

[运行指南](getting_started.md) · [发布说明](publishing.md)
