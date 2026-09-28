# Task: manual-qa 前端评测面板（/metrics tab）

## 背景
RAG 问答 demo 的顶栏要加一个「评测」入口，展示离线评测结果与实时状态。
工作目录 frontend/，Vue3+TS。改 App.vue + style.css，**不引新依赖**。

## 后端数据源（新端点，已由后端提供）
GET /api/metrics 返回：
```json
{
  "offline": {
    "evaluated_at": "2026-09-28",
    "qa_set": "123 题分层 QA 集（37 章分层抽样 + LLM 依种子出题）",
    "metric_note": "章节级 recall@5：top-5 命中正确内容所在章节",
    "configs": [
      {"name": "vector", "label": "纯向量", "recall5": 0.943, "mrr": 0.799},
      {"name": "hybrid", "label": "混合检索(RRF)", "recall5": 0.935, "mrr": 0.803},
      {"name": "hybrid_rewrite", "label": "混合+查询改写", "recall5": 0.935, "mrr": 0.856}
    ],
    "breakdown": [
      {"group": "数值 | 跨语言(中文→英文手册)", "n": 60, "vector": {"r5": 0.9, "mrr": 0.75}, "hybrid_rewrite": {"r5": 0.92, "mrr": 0.8}},
      ...7 组（题型×语料矩阵）
    ]
  },
  "runtime": {"chunks": 105716, "docs": "RM0433 + ESP-IDF", "daily_limit": 30}
}
```
如果 /api/metrics 404，用 mock：`window.__METRICS_MOCK` 形式写在代码里 fallback。

## 页面要求
1. 顶栏右侧加「评测」按钮（和"知识库已连接"并排），点击进入评测视图；评测视图内
   有「返回对话」返回主界面（用组件内 v-if 切换 view: 'chat' | 'metrics'，不引路由）
2. **总体卡**：三配置的 recall@5 与 MRR，用纯 CSS 横条图（div 宽度百分比）对比，
   不用图表库。每条：label + 数值 + 条形（vector 灰 / hybrid 深灰 / hybrid+rewrite 黑）
3. **分层矩阵卡**：breakdown 表格（组名 | n | vector r@5 | hybrid+rw r@5 | Δ），
   Δ 为正显示绿、负显示红（用现有 CSS 变量的灰系，绿=#10b981 红=#ef4444）
4. **口径标注（关键）**：页面顶部显著位置注明
   "离线评测 · 123 题分层 QA 集 · 章节级 recall@5 · 评于 {evaluated_at}"
5. **实时状态卡**：语料块数 / 双语料名 / 每日限流 30 次（静态展示）
6. 视觉延续现有设计语言（var(--bg)灰白底/白卡片/黑主按钮/mono数字），卡片间距 16px
7. 移动端 375px 适配（表格可横向滚动）

## 验收（自查后 commit）
- [ ] 切换视图流畅，主对话功能不受影响（v-if 不卸载对话状态）
- [ ] mock 模式下（后端没起）面板也能完整渲染
- [ ] npm run build 零错误
- [ ] 不改 App.vue 的对话逻辑，只加 view 状态和 metrics 组件区块
- 只动 frontend/ 内文件，git commit 用英文 conventional commits
