"""manual-qa：嵌入式技术手册智能问答助手（可评测 Agentic RAG）。

模块地图（按数据流顺序）：
  ingest/      PDF -> Markdown -> 清洗 -> 分块
  retrieval/   向量检索 + BM25 + 混合融合（RRF）
  generation/  检索增强生成（SSE 流式）
  eval/        QA 测试集 + recall@k / MRR / 忠实度
  api/         FastAPI 服务（REST + SSE）
"""

__version__ = "0.1.0"
