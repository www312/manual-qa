# API 契约 v1（前端据此开发，后端 P3 实现）

Base URL: `http://localhost:8000`（开发期）

## 1. POST /api/ask —— 问答（SSE 流式）

请求：
```json
{ "question": "RCC_APB1ENR 寄存器的地址偏移是多少？", "mode": "hybrid", "k": 5 }
```
- `mode`: `"vector" | "bm25" | "hybrid"`（默认 hybrid）
- `k`: 检索条数，默认 5

响应：`text/event-stream`，按顺序三类事件：

```
event: citations
data: {"citations":[{"n":1,"chunk_id":"rm0433-17878","doc":"rm0433","chapter":"26 DAC > 26.7 DAC registers","page":1079,"score":0.83,"snippet":"...前80字..."},{"n":2,...}]}

event: delta
data: {"text":"APB1 时钟使能寄存器（RCC_APB1ENR）"}

event: delta
data: {"text":"的地址偏移为 0x58 [1]。"}

event: done
data: {"question_id":"q_20260924_001","latency_ms":2340,"tokens":87}
```

- `citations` 先行到达 → 前端可先渲染引用侧栏，答案边流边出
- 引用字段 `n` 与答案内 `[1]` 对应；`snippet` 已截断，悬浮/点击展开用
- 错误：`event: error` + `data: {"message":"..."}`
- 限流（P3）：HTTP 429 + `{"message":"今日额度已用完"}`

## 2. POST /api/search —— 纯检索（调试/对比用）

请求：`{"query":"...", "mode":"hybrid", "k":5}`
响应（普通 JSON）：
```json
{"results":[{"n":1,"chunk_id":"...","doc":"...","chapter":"...","page":1079,"score":0.83,"snippet":"...前200字..."}]}
```

## 3. GET /health —— 存活探测

```json
{"status":"ok","chunks":217321,"index":"manual_chunks","version":"0.1.0"}
```

## 前端页面要求

1. **问答页**：输入框 + 发送；回答区流式打字机渲染；右侧/下方引用卡片列表，
   答案内 `[n]` 标记 hover 高亮对应卡片，卡片点击可展开 snippet 全文
2. **模式切换**：vector / bm25 / hybrid 三选一（Segmented Control），切换后
   同一问题可重发——这是演示「混合检索优势」的交互亮点
3. 流式渲染注意：fetch + ReadableStream 解析 SSE（POST 不能用 EventSource），
   按 `\n\n` 分帧、`event:`/`data:` 两行解析
4. 技术栈：Vue3 + TS + Element Plus + Vite，视觉参考 Linear/Stripe 的简洁风
5. 移动端可用（简历链接手机点开也要能看）
