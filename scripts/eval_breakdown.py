"""分层评测：123 题按 题型 × 语料 切分，产出细分矩阵。

维度：
  - 题型（QA 集生成时标注：数值/条件/步骤）
  - 语料（rm0433=跨语言检索 vs espidf=中文同语言）
对比列：
  - vector（基线）
  - hybrid+rewrite（线上配置）
  注：rerank 为 LLM 调用不便全量跑，抽 20 题示意
"""

import json
import statistics
import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import Retriever
from manual_qa.rewrite import QueryRewriter

qa = [json.loads(l) for l in open("data/qa_dataset_raw.jsonl")]
chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
by_id = {c["chunk_id"]: c for c in chunks}
r = Retriever(chunks)
rw = QueryRewriter()

print(f"loading done, {len(qa)} questions")

# 分组函数
def group_key(item: dict) -> str:
    t = item.get("type", "未知")
    if t not in ("数值", "条件", "步骤"):
        t = "其他"
    lang = "跨语言(中文→英文手册)" if item["doc"] == "rm0433" else "中文同语言(ESP-IDF)"
    return f"{t} | {lang}"

groups: dict[str, list] = {}
for item in qa:
    groups.setdefault(group_key(item), []).append(item)

# 评测两组配置
def eval_group(items: list[dict], mode: str, use_rewrite: bool) -> dict:
    c5s, mrrs = [], []
    for item in items:
        q = item["question"]
        if use_rewrite:
            bm25_q = rw.rewrite(q)
            hits = r.search_dual(q, bm25_q, k=5)
        else:
            hits = r.search(q, k=5, mode=mode)
        ids = [h["chunk_id"] for h in hits]
        gold = item["seed_chunk_id"]
        gold_ch = by_id[gold]["chapter"]
        hit_ids = [i for i in ids if i == gold or by_id[i]["chapter"] == gold_ch]
        c5s.append(1 if hit_ids[:5] else 0)
        mrrs.append(1.0 / (ids.index(hit_ids[0]) + 1) if hit_ids else 0.0)
    return {"n": len(items), "r@5": round(statistics.mean(c5s), 3), "MRR": round(statistics.mean(mrrs), 3)}

results = {}
for gname, items in sorted(groups.items()):
    base = eval_group(items, "vector", False)
    hybrid = eval_group(items, "hybrid", True)
    results[gname] = {"vector": base, "hybrid_rewrite": hybrid}
    print(f"{gname:36s} n={len(items):3d} | vector r@5={base['r@5']:.3f} MRR={base['MRR']:.3f} | hybrid+rw r@5={hybrid['r@5']:.3f} MRR={hybrid['MRR']:.3f}")

with open("data/eval_breakdown.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("written data/eval_breakdown.json")
