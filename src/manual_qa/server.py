"""FastAPI 服务：/api/ask(SSE) + /api/search + /health，接真实 RAG。

设计：
  - 启动时加载 Retriever（BM25 索引建一次）+ RAG；冷启动约 40-60s
  - SSE 事件流严格按 docs/api-contract.md v1
  - 查询改写挂在 hybrid 模式（P2 实验最优配置 C）
  - 停止按钮：客户端断开 → 生成器 GeneratorExit 自动中断
"""

from __future__ import annotations

import json
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from manual_qa.agent import AgentRAG
from manual_qa.generation import RAG
from manual_qa.retrieval import Retriever
from manual_qa.rewrite import QueryRewriter

app = FastAPI(title="manual-qa", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_retriever: Retriever | None = None
_rag: RAG | None = None
_rewriter: QueryRewriter | None = None
_agent: AgentRAG | None = None


def get_rag() -> RAG:
    global _retriever, _rag, _rewriter
    if _rag is None:
        import json as _json

        chunks = [_json.loads(l) for l in open("data/chunks_selected.jsonl")]
        _retriever = Retriever(chunks)
        _rag = RAG(_retriever)
        _rewriter = QueryRewriter()
        globals()["_agent"] = AgentRAG(_retriever)
        assert _retriever is not None and _rewriter is not None
    return _rag


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    mode: str = Field(default="hybrid", pattern="^(vector|bm25|hybrid|agent)$")
    k: int = Field(default=5, ge=1, le=10)


class SearchBody(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    mode: str = Field(default="hybrid", pattern="^(vector|bm25|hybrid)$")
    k: int = Field(default=5, ge=1, le=10)


@app.get("/health")
def health() -> dict:
    n = 105716
    return {"status": "ok", "chunks": n, "index": "manual_chunks", "version": "0.1.0"}


@app.post("/api/ask")
async def ask(body: AskBody):
    rag = get_rag()
    assert _agent is not None
    qid = f"q_{uuid.uuid4().hex[:12]}"
    t0 = time.time()

    async def gen():
        try:
            if body.mode == "agent":
                # Agent 模式：LLM 自主决定是否/如何调用 manual_search
                async for ev in _agent.run(body.question):
                    if ev["type"] == "step":
                        yield {"event": "step", "data": json.dumps(
                            {"kind": ev["kind"], **({"query": ev["query"]} if "query" in ev else {}), **({"text": ev["text"]} if ev.get("text") else {})},
                            ensure_ascii=False,
                        )}
                    elif ev["type"] == "done":
                        cites = [
                            {"n": i + 1, "chunk_id": h["chunk_id"], "doc": h["doc"],
                             "chapter": h["chapter"], "page": h["page"],
                             "score": round(float(h["score"]), 3), "snippet": h["text"][:120]}
                            for i, h in enumerate(ev["citations"])
                        ]
                        yield {"event": "citations", "data": json.dumps({"citations": cites}, ensure_ascii=False)}
                        yield {"event": "done", "data": json.dumps(
                            {"question_id": qid, "latency_ms": int((time.time() - t0) * 1000), "tokens": 0})}
                return

            # 检索（P2 配置C：向量用原查询，BM25 用改写查询）
            hits = (
                _retriever.search_dual(
                    body.question,
                    _rewriter.rewrite(body.question),
                    k=body.k,
                )
                if body.mode == "hybrid"
                else _retriever.search(body.question, k=body.k, mode=body.mode)
            )
            cites = [
                {
                    "n": i + 1,
                    "chunk_id": h["chunk_id"],
                    "doc": h["doc"],
                    "chapter": h["chapter"],
                    "page": h["page"],
                    "score": round(float(h["score"]), 3),
                    "snippet": h["text"][:120],
                }
                for i, h in enumerate(hits)
            ]
            yield {"event": "citations", "data": json.dumps({"citations": cites}, ensure_ascii=False)}

            # 流式生成
            tok = 0
            async for delta in rag.astream(body.question, hits):
                tok += 1
                yield {"event": "delta", "data": json.dumps({"text": delta}, ensure_ascii=False)}

            yield {
                "event": "done",
                "data": json.dumps(
                    {"question_id": qid, "latency_ms": int((time.time() - t0) * 1000), "tokens": tok},
                ),
            }
        except Exception as ex:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps({"message": str(ex)[:200]}, ensure_ascii=False)}

    return EventSourceResponse(gen())


@app.post("/api/search")
def search(body: SearchBody) -> dict:
    rag = get_rag()
    hits = _retriever.search(body.query, k=body.k, mode=body.mode)
    return {
        "results": [
            {
                "n": i + 1,
                "chunk_id": h["chunk_id"],
                "doc": h["doc"],
                "chapter": h["chapter"],
                "page": h["page"],
                "score": round(float(h["score"]), 3),
                "snippet": h["text"][:200],
            }
            for i, h in enumerate(hits)
        ]
    }
