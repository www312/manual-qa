# Task: manual-qa 前端问答界面开发

## 项目背景
嵌入式技术手册智能问答系统（RAG）。后端 FastAPI 提供 SSE 流式问答接口，
你现在开发 Vue3 前端。**后端尚未就绪**，所以你必须同时提供一个
mock 模式的 SSE 服务（Node 脚本或 vite dev server 中间件均可），
让页面在没有后端时也能完整演示。

## 位置与技术栈
- 工作目录：`frontend/`（Vite + Vue3 + TS + Element Plus 已装好）
- 严格 TS，禁止 any（可 `as` 断言到具体类型）

## API 契约（必须严格遵守，见 ../docs/api-contract.md）
POST http://localhost:8000/api/ask
body: {"question": string, "mode": "vector"|"bm25"|"hybrid", "k": number}
SSE 事件序列：citations -> (delta x N) -> done；错误 event: error
- citations: {citations: [{n, chunk_id, doc, chapter, page, score, snippet}]}
- delta: {text: string}
- done: {question_id, latency_ms, tokens}

## 页面要求
1. 问答页（核心）：
   - 顶部标题「嵌入式手册智能问答」+ 副标题（语料：STM32H743 RM0433 + ESP-IDF，共 21.7 万块）
   - 对话区：用户问题右对齐气泡；回答流式打字机渲染（SSE delta 追加）
   - 回答内联引用标记 [n] 渲染为可交互 sup 元素，hover 时右侧引用卡片高亮
   - 引用卡片列表（回答下方折叠面板）：n / doc 图标 / chapter / page / score 百分比 / snippet（点击展开全文）
   - 底部输入区：textarea 自适应高度 + 发送按钮（Enter 发送 / Shift+Enter 换行）+ 停止按钮（流式中可中断，AbortController）
2. 检索模式切换：vector / bm25 / hybrid 三选一 Segmented，切换后可「用当前模式重问」
3. 空状态：首次进入显示 3 个示例问题卡片（点击直接提问）
4. 加载态：citations 到达前显示骨架屏；流式期间输入框禁用
5. 移动端适配（max-width 768px 单栏）
6. 视觉：简洁工具风，参考 Linear——白底/暗色皆可但全局统一，主色 #4F6EF7，圆角 8px，卡片浅阴影

## Mock 模式（必须实现）
- `frontend/mock/server.mjs`：Node http server，端口 8000，实现 /api/ask 的 SSE
  （citations 给 3 条假数据，delta 每 80ms 吐一段中文假答案含 [1][2] 标记，最后 done）
- vite.config.ts 加 proxy：/api -> localhost:8000
- `npm run mock` 启动 mock；README 写清「无后端演示：npm run mock + npm run dev」

## 验收（自查后再交）
- [ ] npm run build 零错误
- [ ] mock 模式下完整问答流程可演示：citations 骨架屏 -> 流式答案 -> 引用交互
- [ ] 模式切换/停止/Enter 发送/示例问题全部可用
- [ ] 移动端 375px 宽度布局不破
- 不要动 frontend/ 以外的任何文件。完成后 git commit（信息用英文 conventional commits）。
