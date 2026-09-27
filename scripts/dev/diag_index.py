"""诊断入库卡点：分块后统计 token 分布 + embedding 吞吐实测。"""

import json
import time

from manual_qa.config import load_settings
from manual_qa.llm import EmbeddingClient, _n_tokens

texts = [json.loads(l)["text"] for l in open("data/chunks.jsonl")]
lens = [_n_tokens(t) for t in texts]
lens.sort()
n = len(lens)
print(f"chunks={n}  p50={lens[n//2]}  p90={lens[int(n*0.9)]}  p99={lens[int(n*0.99)]}  max={lens[-1]}")
over = sum(1 for x in lens if x > 6000)
print(f"over 6000 tok: {over}")

s = load_settings()
e = EmbeddingClient(s.embed)
t0 = time.time()
v = e.embed(texts[:320])
dt = time.time() - t0
print(f"320 texts in {dt:.1f}s -> {320/dt:.1f} texts/s, ETA for {n}: {n/(320/dt)/60:.0f} min")
