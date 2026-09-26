"""端到端 RAG 问答验证（glm-4.7 生成 + 引用）。"""

import json
import sys

sys.path.insert(0, "src")

from manual_qa.generation import RAG
from manual_qa.retrieval import Retriever

chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
r = Retriever(chunks)
rag = RAG(r)

for q in [
    "RCC_APB1ENR 寄存器的地址偏移是多少？",
    "ESP32 怎么进入 Light-sleep 低功耗模式？",
]:
    print(f"\n{'='*70}\nQ: {q}")
    out = rag.ask(q, k=5, mode="hybrid")
    print(f"A: {out['answer'][:500]}")
    print(f"\n引用 {len(out['citations'])} 条:")
    for h in out["citations"][:3]:
        print(f"  [{h['chunk_id']}] {h['chapter'][:50]} p{h['page']}")
