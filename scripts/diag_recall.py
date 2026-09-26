"""诊断低 recall：miss 的题，top-10 里有没有与种子同章节/同页的块？

如果同章节块大量存在 → 金标"种子块精确命中"太严，需补章节级 recall；
如果同章节也没有 → 检索真的差，P2 空间大。两种结论都关键。
"""

import json
import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import Retriever

qa = [json.loads(l) for l in open("data/qa_dataset_raw.jsonl")]
chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
by_id = {c["chunk_id"]: c for c in chunks}
r = Retriever(chunks)

sample = qa[:30]
strict_hit = sect_hit = neither = 0
for item in sample:
    hits = r.search(item["question"], k=10, mode="vector")
    ids = [h["chunk_id"] for h in hits]
    gold = item["seed_chunk_id"]
    gold_ch = by_id[gold]["chapter"]
    if gold in ids:
        strict_hit += 1
    elif any(by_id[i]["chapter"] == gold_ch for i in ids if i in by_id):
        sect_hit += 1
    else:
        neither += 1
        if neither <= 3:
            print(f"MISS: {item['question'][:60]}")
            print(f"  gold: {gold_ch[:60]} p{by_id[gold]['page']}")
            print(f"  top1: {hits[0]['chapter'][:60]} p{hits[0]['page']}")

print(f"\n30题抽样: 严格命中={strict_hit} 同章节命中={sect_hit} 全未命中={neither}")
