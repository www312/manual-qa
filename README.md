# manual-qa — 嵌入式技术手册智能问答（可评测 Agentic RAG）

对 **STM32H743 参考手册（RM0433, 3353 页）** 与 **ESP-IDF 编程指南（2855 页，中文）** 建立的 RAG 问答系统：混合检索 + LLM 查询改写 + 全链路评测 + 引用溯源 + SSE 流式服务 + Web 前端 + MCP 工具接口。

所有指标来自可复现实验（`data/eval_*.json`），无一手填。

## 架构

```
PDF 手册 ─→ PyMuPDF 解析 ─→ 清洗(页眉页脚/目录点线/表格→MD) ─→ 书签层级感知分块
                                                                        │ (105,716 块 / 50.5M tokens)
              Embedding(智谱 embedding-3, 2048维) ──────────→ Qdrant(本地模式)
                                                                        │
检索:  向量 TopK(原查询) ┐
                        ├─→ RRF 融合(k=60) ─→ glm-4.7 生成(引用溯源[n], SSE)
      BM25(改写查询)  ──┘    ↑
              LLM 查询改写(中文问题 → 英文检索词)
评测:  123 题 QA 集 → recall@k / MRR / 双口径(块级/章节级)
服务:  FastAPI(SSE) + Vue3 前端 + MCP Server
```

## 评测结果（123 题，全部可复现）

| 配置 | 块级 recall@5 | 章节级 recall@5 | MRR |
|---|---|---|---|
| 纯向量（基线） | 9.8% | 94.3% | 0.799 |
| hybrid（BM25+向量 RRF） | 7.3% | 93.5% | 0.803 |
| **hybrid + 查询改写（最优）** | **13.0% (+33%)** | **93.5%** | **0.856** |
| 纯 BM25 + 查询改写（对照组） | 13.0% | 54.5% | 0.614 |

关键工程结论：

- **评测口径决定结论**：块级（精确命中种子块）vs 章节级（命中正确内容所在章节）差异巨大，先修口径再优化，否则方向全错
- **BM25 跨语言三坑**：①jieba 切碎寄存器名 ②中文虚词在英文语料中成"稀有词"被 IDF 反向加权 ③词法匹配的结构性极限——前两个是 bug（修后 9.8%→24.4%），第三个只能靠查询改写补
- **RRF 融合的价值**：向量兜语义底线，BM25 补精确符号命中；对照组证明单路都不够

## 快速启动

```bash
# 后端（Python 3.12, uv）
uv sync
cp .env.example .env   # 填入智谱 API key
uv run python -m manual_qa.index        # 入库（首次 ~50min，embedding API）
uv run uvicorn manual_qa.server:app --port 8000

# 前端
cd frontend && npm install && npm run dev

# 无后端快速体验（mock 数据）
cd frontend && npm run mock & npm run dev
```

## API

- `POST /api/ask` — SSE 流式问答（citations → delta* → done）
- `POST /api/search` — 纯检索（vector / bm25 / hybrid）
- `GET /health` — 存活探测
- MCP：`manual_search` 工具（stdio）

## 项目结构

```
src/manual_qa/
  ingest.py       # PDF 解析/清洗/层级分块（书签骨架 + 表格→MD + tiktoken 精确分块）
  index.py        # Qdrant 入库（本地模式，零 Docker 依赖）
  retrieval.py    # 向量/BM25/RRF 混合检索 + 保形分词器
  rewrite.py      # LLM 查询改写（缓存）
  generation.py   # RAG 生成（引用溯源 + SSE）
  gen_questions.py # QA 评测集生成（分层抽样种子块 + LLM 出题）
  evaluate.py     # recall@k / MRR 双口径评测器
  server.py       # FastAPI 服务
```

## 语料与成本

全量分块 21.7 万块（RM0433 表格密集），按章节价值精选 105,716 块入库（寄存器/外设/配置章节优先，剔除目录/修订页）——预算约束下的工程取舍。embedding 总消耗 ~50.5M tokens。
