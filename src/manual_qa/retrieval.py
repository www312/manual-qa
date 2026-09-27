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


# 中文停用词：出题语言（中文）的高频虚词在英文语料中反而成了“稀有词”，
# IDF 加权后严重干扰 BM25 打分（诊断：'的/是/多少' 把 HSEM 题顶到了蓝牙章节）。
_CN_STOP = set(
    "的 是 多少 什么 怎么 如何 哪些 对于 关于 以及 或者 但是 如果 请问 "
    "地址 偏移 寄存器 位 值 类型 中 在 上 下 里 和 与 也 都 就 会 可 可以 "
    "返回 软件 读取 进行 使用 设置 配置 进入 输出 输入".split()
)


def _tokenize(text: str, drop_stop: bool = False) -> list[str]:
    """混合分词：连续 ASCII 串（寄存器名/API名/路径）保持整词，中文走 jieba。

    drop_stop=True 时剔除中文停用词（BM25 索引与查询两侧都开）。
    教训：纯 jieba.cut_for_search 会把 RCC_APB1ENR 切成碎片；虚词不剔会
    让中文查询在英文语料上被 IDF 带偏。
    """
    out: list[str] = []
    buf = ""          # ASCII 连续串缓冲
    cbuf = ""         # 非ASCII 连续串缓冲（中文短语）
    for ch in text:
        if ch.isascii() and (ch.isalnum() or ch in "_-.@/"):
            if cbuf:
                out.extend(t for t in jieba.cut(cbuf) if t.strip())
                cbuf = ""
            buf += ch
        else:
            if buf:
                out.append(buf.lower())
                buf = ""
            if not ch.isspace():
                cbuf += ch
    if buf:
        out.append(buf.lower())
    if cbuf:
        out.extend(t for t in jieba.cut(cbuf) if t.strip())
    if drop_stop:
        out = [t for t in out if t not in _CN_STOP]
    return out


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

        # BM25 索引（启动时建一次；两侧同用停用词过滤）
        self.bm25 = BM25Okapi([_tokenize(c["text"], drop_stop=True) for c in chunks])
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
        scores = self.bm25.get_scores(_tokenize(query, drop_stop=True))
        top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self._bm25_ids[i], scores[i]) for i in top if scores[i] > 0]

    def search_dual(
        self, query_vec: str, query_lex: str, k: int | None = None
    ) -> list[dict]:
        """P2 实验配置 C 的线上形态：向量侧用原查询（语义），BM25 侧用改写查询（词法）。"""
        k = k or self.settings.retrieval.top_k
        rrf_k = self.settings.retrieval.rrf_k
        vr = self._vector(query_vec, k * 2)
        br = self._bm25_search(query_lex, k * 2)
        agg: dict[str, float] = {}
        for rank, (cid, _) in enumerate(vr):
            agg[cid] = agg.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        for rank, (cid, _) in enumerate(br):
            agg[cid] = agg.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        ranked = sorted(agg.items(), key=lambda x: -x[1])[:k]
        by_id = {c["chunk_id"]: c for c in self.chunks}
        return [{**by_id[cid], "score": sc} for cid, sc in ranked if cid in by_id]

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
