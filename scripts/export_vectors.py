"""本地把 Qdrant local(sqlite) 数据导出为可上传的 JSONL 向量文件，
服务器端用 Qdrant server API 批量 upsert——零 embedding 成本迁移。

输出: data/vectors_export.jsonl (chunk_id + vector + payload)
体积估计 ~1.5G（2048维 float 每条 ~8KB 文本 + 向量）
"""

import json
import sys

import numpy as np
from qdrant_client import QdrantClient

sys.path.insert(0, "src")

client = QdrantClient(path="data/qdrant")

out = open("data/vectors_export.jsonl", "w")
n = 0
offset = None
while True:
    pts, offset = client.scroll(
        collection_name="manual_chunks",
        limit=256,
        offset=offset,
        with_payload=True,
        with_vectors=True,
    )
    if not pts:
        break
    for p in pts:
        vec = p.vector
        if vec is None:
            continue
        rec = {
            "id": p.id,
            "vector": np.asarray(vec, dtype=np.float32).tolist(),
            "payload": p.payload,
        }
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        n += 1
    if offset is None:
        break
out.close()
print(f"exported {n} points -> data/vectors_export.jsonl")
