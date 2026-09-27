"""诊断：保形分词后 BM25 为何仍只有 7.3%？

假设：英文手册正文里 ASCII 串之间夹着标点/空格，正文侧 token 是碎片化的小词
（"The DAC channel"），而查询侧寄存器名整词命中需要正文里也出现同形 token。
抽 5 个题看 BM25 top-5 与查询 token 的匹配情况。
"""

import json
import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import Retriever, _tokenize

qa = [json.loads(l) for l in open("data/qa_dataset_raw.jsonl")]
chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
by_id = {c["chunk_id"]: c for c in chunks}
r = Retriever(chunks)

for item in qa[:5]:
    q = item["question"]
    qt = _tokenize(q)
    hits = r.search(q, k=3, mode="bm25")
    gold_ch = by_id[item["seed_chunk_id"]]["chapter"]
    top_ch = hits[0]["chapter"] if hits else "NONE"
    hit_txt = hits[0]["text"][:150] if hits else ""
    # 查询 token 有几个出现在 top1 正文里
    tt = set(_tokenize(hits[0]["text"])) if hits else set()
    overlap = [t for t in qt if t in tt]
    print(f"Q: {q[:50]}")
    print(f"  qtokens({len(qt)}): {' '.join(qt[:12])}")
    print(f"  overlap in top1: {overlap[:8]}")
    print(f"  gold: {gold_ch[:45]} | top1: {top_ch[:45]}")
    print()
