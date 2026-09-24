"""向量入库：Qdrant 本地模式 + 智谱 embedding。

设计：
  - 本地模式（path 落盘）零 Docker 依赖，开发期即开即用；P3 换 server 模式
    只改一个 QdrantClient 构造参数——接口不变是刻意设计。
  - 建集合维度 2048（embedding-3 实测值，文档写 2560 是错的）。
  - 分批 embed（批量 64）+ upsert，全程可重跑（先删后建）。
"""

from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient, models

from manual_qa.config import load_settings
from manual_qa.ingest import Chunk
from manual_qa.llm import EmbeddingClient


def get_client(path: Path) -> QdrantClient:
    return QdrantClient(path=str(path))


def build_index(chunks: list[Chunk], dim: int = 2048) -> dict:
    s = load_settings()
    emb = EmbeddingClient(s.embed)
    client = get_client(s.store.qdrant_path)
    col = s.store.collection

    if client.collection_exists(col):
        client.delete_collection(col)
    client.create_collection(
        collection_name=col,
        vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
    )

    texts = [c.text for c in chunks]
    vectors = emb.embed(texts)  # 内部分批+重试

    points = [
        models.PointStruct(
            id=i,
            vector=v,
            payload={
                "chunk_id": c.chunk_id,
                "doc": c.doc,
                "chapter": c.chapter,
                "page": c.page,
                "text": c.text,
            },
        )
        for i, (c, v) in enumerate(zip(chunks, vectors, strict=True))
    ]
    B = 256
    for i in range(0, len(points), B):
        client.upsert(col, points=points[i : i + B])

    info = client.get_collection(col)
    return {"points": info.points_count, "collection": col}


if __name__ == "__main__":
    import json
    import time

    from manual_qa.ingest import ingest_pdf

    t0 = time.time()
    all_chunks: list[Chunk] = []
    for path, doc in [
        ("data/raw/rm0433.pdf", "rm0433"),
        ("data/raw/esp-idf-zh_CN-v5.0.9-esp32.pdf", "espidf"),
    ]:
        cs = ingest_pdf(path, doc)
        print(f"{doc}: {len(cs)} chunks ({time.time()-t0:.0f}s)")
        all_chunks.extend(cs)

    # 落盘一份 chunk 快照（评测与调试用，不进 git）
    out = Path("data/chunks.jsonl")
    with out.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(
                json.dumps(
                    {
                        "chunk_id": c.chunk_id,
                        "doc": c.doc,
                        "chapter": c.chapter,
                        "page": c.page,
                        "text": c.text,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"chunks.jsonl written: {out}")

    stats = build_index(all_chunks)
    print(f"qdrant: {stats} ({time.time()-t0:.0f}s total)")
