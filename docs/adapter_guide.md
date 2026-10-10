# 网页接入与新增Adapter

网页方式可以直接体验很多AI产品，不依赖产品API开放。但不同页面需要具体适配；当前仅验证原有两款指定应用，未实现任意URL自动适配。

当前Adapter接口：
- `begin(question,index)`：建立当前轮起点、记录已有问题/回答数。
- `observe()`：输入就绪、是否填好、发送可用、是否已发送、答案就绪、阻塞、原始回答。
- `execute(action)`：再次观察并验证动作仍合法；状态变化时重新决策，禁止重复发送。
- `snapshot(label)`：保存过程证据。
- `end()`：移除本轮监听。

新增具体网页：
1. 观察真实页面，识别输入框、发送按钮、当前轮问题与回答区域、生成状态。
2. 实现独立Adapter；可以继承现有安全执行与截图方法，但不要未经检查复用回答完成判据。
3. 在 `adapters.py` 的 `ADAPTERS` 与 `COMPLETION_BASES` 注册同一产品ID。
4. 在Notebook `products` 添加网址和配置，再加入 `SELECTED_PRODUCTS`。
5. 先用一个任务检查发送一次、只读当前轮回答、回答结束判据和追问会话；再扩充矩阵。

任务、Persona、评测与报告无需为每个新产品重新编写。若产品需要文件上传、登录或外部工具调用，应扩展明确动作与状态，不假装原有文本问答接口已经覆盖。


## 独立网页检查与手动操作

```bash
python tools/inspect_page.py --url https://example.com --output-root evaluation/page_inspection --manual
```

将 URL 换成目标网页。在浏览器中可手动操作；操作结束后在 Inspector 点击 Resume，工具保存页面文本、控件和截图。这个入口保留了早期的手动查看方式，不会自动发送评测问题，不会把任意页面自动转成完整 Adapter，也不将登录状态自动接入批量评测。

当前代码入口为 `evaluator/adapters.py` 与 `evaluator/adapter_contract.py`。应用需登录时，还应在该 Adapter 中明确会话准备与等待方式，不将个人 Cookie 放入公开仓库。
