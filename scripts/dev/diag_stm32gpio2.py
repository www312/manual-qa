"""深挖：分词修复后 BM25 侧的 token 匹配情况 + 向量路为什么仍偏 ESP。"""

import json
import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import Retriever, _tokenize

chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
r = Retriever(chunks)

q = "STM32GPIO 有多少个引脚"
print("A. 纯 BM25（分词修复后）:")
for h in r.search(q, k=3, mode="bm25"):
    print(f"   {h['doc']:6s} {h['chapter'][:50]} p{h['page']}")

# BM25 token 视角：rm0433 里 gpio/stm32 出现密度
qt = set(_tokenize(q, drop_stop=True))
print("\nB. 查询 token:", sorted(qt))
for doc in ("rm0433", "espidf"):
    n_gpio = sum(1 for c in chunks if c["doc"] == doc and "gpio" in _tokenize(c["text"], drop_stop=True)[:50])
    print(f"   {doc}: 含 gpio 的块 ~{n_gpio}")
