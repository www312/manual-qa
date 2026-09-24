"""检索层：向量检索 + BM25 + RRF 混合（P2 前置实现，P1 先只用向量做基线）。

设计（面试考点）：
  - 为什么混合：向量检索管语义（"怎么让芯片睡眠" ↔ 低功耗模式），
    BM25 管精确符号（寄存器名 RCC_APB1ENR、Kconfig 选项名）。
    嵌入式手册问答两类查询都高频，单一检索器各有盲区。
  - RRF（Reciprocal Rank Fusion）：score = Σ 1/(k + rank_i)，k=60。
    只用排名不用原始分，天然免疫两边分数量纲差异——无需调权重，
    这是它比线性加权稳的原因。
"""

from __future__ import annotations

import jieba
from qdrant_client import models
from rank_bm25 import BM25Okapi

from manual_qa.config import load_settings
from manual_qa.llm import EmbeddingClient


def _tokenize(text: str) -> list[str]:
    """jieba 分词 + 小写化；英文符号（寄存器名等）保持整词。"""
    return [t.lower() for t in jieba.cut_for_search(text) if t.strip()]


class Retriever:
    """统一检索接口：search(query, k, mode='vector'|'bm25'|'hybrid')。"""

    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        s = load_settings()
        self.settings = s
        self.embedder = EmbeddingClient(s.embed)

        from manual_qa.index import get_client

        self.qd = get_client(s.store.qdrant_path)
        self.collection = s.store.collection

        # BM25 索引（启动时建一次）
        self.bm25 = BM25Okapi([_tokenize(c["text"]) for c in chunks])
        self._bm25_ids = [c["chunk_id"] for c in chunks]

    def _vector(self, query: str, k: int) -> list[tuple[str, float]]:
        qv = self.embedder.embed_query(query)
        res = self.qd.query_points(
            self.collection,
            query=qv,
            limit=k,
            with_payload=True,
        )
        pts = res.points or []
        return [(p.payload["chunk_id"], p.score) for p in pts if p.payload]

    def _bm25_search(self, query: str, k: int) -> list[tuple[str, float]]:
        scores = self.bm25.get_scores(_tokenize(query))
        top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self._bm25_ids[i], scores[i]) for i in top if scores[i] > 0]

    def search(
        self, query: str, k: int | None = None, mode: str = "vector"
    ) -> list[dict]:
        k = k or self.settings.retrieval.top_k
        if mode == "vector":
            ranked = self._vector(query, k)
        elif mode == "bm25":
            ranked = self._bm25_search(query, k)
        elif mode == "hybrid":
            # 两路各取 top-2k，RRF 融合
            rrf_k = self.settings.retrieval.rrf_k
            vr = self._vector(query, k * 2)
            br = self._bm25_search(query, k * 2)
            agg: dict[str, float] = {}
            for rank, (cid, _) in enumerate(vr):
                agg[cid] = agg.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
            for rank, (cid, _) in enumerate(br):
                agg[cid] = agg.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
            ranked = sorted(agg.items(), key=lambda x: -x[1])[:k]
        else:
            raise ValueError(f"unknown mode: {mode}")

        by_id = {c["chunk_id"]: c for c in self.chunks}
        return [
            {**by_id[cid], "score": sc} for cid, sc in ranked if cid in by_id
        ]


if __name__ == "__main__":
    import json
    import sys

    q = sys.argv[1] if len(sys.argv) > 1 else "RCC_APB1ENR 寄存器的地址偏移是多少"
    mode = sys.argv[2] if len(sys.argv) > 2 else "hybrid"
    chunks = [json.loads(l) for l in open("data/chunks.jsonl")]
    r = Retriever(chunks)
    for mode_i in (["vector", "bm25", "hybrid"] if mode == "all" else [mode]):
        hits = r.search(q, k=5, mode=mode_i)
        print(f"\n=== {mode_i} ===")
        for h in hits:
            print(f"{h['score']:.4f} | {h['chunk_id']} | {h['chapter'][:50]} | p{h['page']}")
            print("   ", h["text"][:100].replace("\n", " "))
