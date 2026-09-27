"""诊断 Q6/Q7 拒答：检索命中 HRTIM 章节但模型拒答——看喂给模型的 top5 是什么内容。"""

import json
import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import Retriever

chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
r = Retriever(chunks)

hits = r.search("HRTIM 定时器的输入时钟频率范围是多少？", k=5, mode="hybrid")
for h in hits:
    print(f"[{h['score']:.3f}] {h['chapter'][:58]} p{h['page']}")
    print("   ", h["text"][:180].replace("\n", " "))
    print()
