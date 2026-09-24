# manual-qa 项目计划 v1（2026-09-24）

定位：把简历上的「嵌入式技术手册智能问答助手」从 RAG 流水线描述升级为
**可评测的 Agentic RAG 系统**——所有数字来自真实实验，可复现、可防守。

## 一、简历叙事（目标态 bullet 预览）

| 现在 | 目标 |
|---|---|
| "设计离线数据处理流水线…" | "构建标题层级感知的分块策略（对比固定窗口，recall@5 +Xpt）" |
| "OpenAI Embeddings + Qdrant，5000+块" | "5000+ 文档块混合检索（BM25+向量 RRF 融合），recall@5 从 X% 提升至 Y%" |
| "Top-K 检索 + GPT-4.1 生成" | "建立 80+ 题 QA 评测集与忠实度自动评审，端到端量化检索与生成质量" |
| （无） | "将检索能力封装为 MCP Server，可被外部 Agent 调用；SSE 流式 + Docker 一键部署" |

（X/Y 留空——数字由实验产出，不预先编造）

## 二、技术架构

```
PDF 手册 ─→ PyMuPDF 解析 ─→ 清洗(去页眉页脚/修订页/表格→MD) ─→ 层级感知分块
                                                                    │
                    ┌───────────────────────────────────────────────┘
                    ▼
        Embedding(智谱 embedding-3, 2048维) ─→ Qdrant(本地模式)
                    │
检索: 向量TopK ┐
              ├─→ RRF 融合 ─→ (可选)重排 ─→ glm-4.7 生成(引用溯源, SSE)
BM25(jieba) ─┘
评测: QA集(80-120题) → recall@k / MRR / 忠实度 → 基线 vs 升级对比报告
服务: FastAPI(REST+SSE) + MCP Server + Docker compose + CI
```

## 三、分阶段计划（每阶段含验收标准）

### P0 数据层（约 1-2 次会话）
- 下载语料：ST RM0433（3353 页，英文，直链已验证）+ ESP-IDF 中文编程指南（官方中文）
- PyMuPDF 布局模式解析：保留标题层级、代码块、表格
- 清洗规则：页眉页脚、目录页、修订记录页剔除；HTML/嵌套表格 → Markdown
- 分块：markdown 标题层级感知 + 512 token 窗口 + 64 overlap（对比固定窗口切法）
- Qdrant 本地模式入库（无 Docker 依赖）
- **验收**：块数 ≥5000；抽样 20 块人工检查（无乱码、表格完整、边界合理）；ingest CLI 可重复执行

### P1 评测层（重点，约 2 次会话）
- QA 测试集：LLM 按章节自动生成候选题（中文 60 + 英文 40），人工筛除坏题，标注标准答案 chunk id
- 基线 RAG：纯向量 Top-5
- 检索指标：recall@5 / recall@10 / MRR
- 生成指标：引用命中率 + LLM-as-judge 忠实度（1-5 分）
- **验收**：产出基线报告（JSON + MD 表），数字真实可复现，命令一条重跑

### P2 检索升级（约 2 次会话）
- BM25（jieba 分词，英文自动切词）+ 向量 → RRF 融合（k=60）
- 查询改写：多查询扩展（1 题改 3 个变体分别检索再融合）
- 重排（二选一，按成本定）：LLM listwise 重排 / 本地 BGE-reranker
- A/B 对比实验：基线 vs +BM25 vs +改写 vs +重排，逐项叠加
- **验收**：recall@5 提升 ≥5pt 才算升级成立；产出对比表（进 README 与简历）

### P3 服务与 Agent 化（约 2 次会话）
- FastAPI：POST /api/ask（SSE 流式+引用）、POST /api/search、GET /health
- MCP Server：manual_search 工具暴露，Claude 等外部 Agent 可挂载
- Web UI 单页：问答框 + 流式渲染 + 引用块高亮
- Docker compose（app + qdrant）、GitHub Actions（ruff + pytest）、开源 README
- **验收**：`docker compose up` 一键起；CI 绿；MCP 工具真实调通截图留档

## 四、语料与成本

| 项 | 方案 | 说明 |
|---|---|---|
| 主语料 | STM32H743 RM0433（3353 页） | 官方直链，寄存器/外设/时钟问题密集 |
| 中文语料 | ESP-IDF 编程指南 PDF | 乐鑫官方中文，QA 集可做中英跨语言检索 |
| API 成本 | 预计 <15 元 | embedding 5000 块 ≈1.3 元；评测生成 100 题×4 配置 ≈10 元 |

## 五、风险与边界

- 大 PDF 表格解析质量 → PyMuPDF 布局模式 + 抽样验收，坏块率 >5% 则引入 pdfplumber 兜底
- 智谱无 rerank API → P2 重排用 LLM 重排或本地模型，不阻塞主线
- 评测数字必须真实：所有简历数字来自 eval 报告留档，绝不手填

## 六、里程碑

P0 数据层 → P1 基线数字（回填简历第一批数字）→ P2 升级数字（简历对比句）
→ P3 开源上线（GitHub repo + README 徽章全绿）→ 面试拷问清单（每条 bullet 的追问+答案）
