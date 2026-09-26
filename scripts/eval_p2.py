"""P2 评测：查询改写 + 混合检索的组合实验。

对比四种配置（同一 QA 集、同一检索器）：
  A. vector（基线）
  B. hybrid 原始查询（BM25 中文问英文库，结构性短板）
  C. hybrid + 查询改写（BM25 侧用英文检索词）
  D. bm25 + 查询改写（纯 BM25 上限参考）
"""

import json
import sys

sys.path.insert(0, "src")

from manual_qa.evaluate import eval_mode
from manual_qa.retrieval import Retriever
from manual_qa.rewrite import QueryRewriter

qa = [json.loads(l) for l in open("data/qa_dataset_raw.jsonl")]
chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
by_id = {c["chunk_id"]: c for c in chunks}
r = Retriever(chunks)
rw = QueryRewriter()
print(f"QA set: {len(qa)}")

results = {}
results["A_vector"] = eval_mode(r, qa, "vector", by_id=by_id)
results["B_hybrid_raw"] = eval_mode(r, qa, "hybrid", by_id=by_id)
results["C_hybrid_rewrite"] = eval_mode(r, qa, "hybrid", by_id=by_id, rewriter=rw)
results["D_bm25_rewrite"] = eval_mode(r, qa, "bm25", by_id=by_id, rewriter=rw)

for name, res in results.items():
    print(
        f"{name:18s} 块级r@5={res['recall@5']:.3f}  章节r@5={res['chapter_recall@5']:.3f}  "
        f"MRR={res['MRR']:.3f}  miss={len(res['misses'])}"
    )

with open("data/eval_p2.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print("written data/eval_p2.json")
