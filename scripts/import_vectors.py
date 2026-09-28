"""服务器端：从导出的 jsonl 批量重建 Qdrant server 集合（零 embedding 成本）。

在 app 容器外的主机上跑（python3 + requests）：
  gunzip vectors_export.jsonl.gz
  python3 import_vectors.py
"""

import json
import sys
import urllib.request

QDRANT = "http://localhost:6333"
COLL = "manual_chunks"
BATCH = 128


def api(path: str, method: str = "GET", body: bytes | None = None) -> dict:
    req = urllib.request.Request(
        QDRANT + path, data=body, method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


# 建集合（幂等：存在则跳过）
try:
    api(f"/collections/{COLL}", "PUT", json.dumps({
        "vectors": {"size": 2048, "distance": "Cosine"}
    }).encode())
    print("collection created")
except Exception as ex:
    if "already exists" in str(ex):
        print("collection exists, skip")
    else:
        raise

n = 0
buf = []
with open("/home/ubuntu/vectors_export.jsonl", encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        buf.append({"id": rec["id"], "vector": rec["vector"], "payload": rec["payload"]})
        if len(buf) >= BATCH:
            api(f"/collections/{COLL}/points?wait=true", "PUT",
                json.dumps({"points": buf}).encode())
            n += len(buf)
            buf = []
            if n % 12800 == 0:
                print(f"  {n} points...")
if buf:
    api(f"/collections/{COLL}/points?wait=true", "PUT",
        json.dumps({"points": buf}).encode())
    n += len(buf)

print(f"imported {n} points")
info = api(f"/collections/{COLL}")
print("count:", info["result"]["points_count"])
