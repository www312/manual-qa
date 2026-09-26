"""P0 收口验证：检索三模式真实查询 + RAG 端到端问答。

查询设计覆盖两类典型场景：
  1. 精确符号查询（BM25 应强）：寄存器名
  2. 语义查询（向量应强）：中文口语问英文手册内容
"""

import json
import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import Retriever

chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
print(f"loading {len(chunks)} chunks...")
r = Retriever(chunks)
print("retriever ready\n")

queries = [
    ("RCC_APB1ENR register address offset", "精确符号"),
    ("怎么进入低功耗模式 睡眠 停止", "中文语义→英文手册"),
    ("SPI flash 初始化步骤", "中文语义（ESP-IDF）"),
]

for q, tag in queries:
    print(f"{'='*70}\n[{tag}] {q}")
    for mode in ["vector", "bm25", "hybrid"]:
        hits = r.search(q, k=3, mode=mode)
        tops = " | ".join(f"{h['chunk_id']}({h['score']:.2f})" for h in hits[:3])
        print(f"  {mode:7s}: {tops}")
    h0 = r.search(q, k=1, mode="hybrid")[0]
    print(f"  hybrid top1 出处: {h0['chapter'][:60]} p{h0['page']}")
    print(f"  正文预览: {h0['text'][:120].replace(chr(10), ' ')}")
