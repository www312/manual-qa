"""P1 评测层 Step2：检索评测器——recall@k / MRR / 命中率。

指标定义（面试考点，别背混）：
  - recall@k   ：top-k 结果里是否含金标块（种子块）。二值，再取平均。
  - MRR        ：金标块第一次出现的排名的倒数。衡量"排得多靠前"。
  - 未命中率   ：k=10 仍未命中的题——这些就是 P2 要攻的坏案例。
"""

from __future__ import annotations

import json
import statistics
import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import Retriever


def eval_mode(r: Retriever, qa: list[dict], mode: str, k: int = 10) -> dict:
    recalls5, recalls10, rrs, misses = [], [], [], []
    for item in qa:
        hits = r.search(item["question"], k=k, mode=mode)
        ids = [h["chunk_id"] for h in hits]
        gold = item["seed_chunk_id"]
        if gold in ids[:5]:
            recalls5.append(1)
        else:
            recalls5.append(0)
        if gold in ids:
            recalls10.append(1)
            rrs.append(1.0 / (ids.index(gold) + 1))
        else:
            recalls10.append(0)
            misses.append(item["question"][:50])
    return {
        "mode": mode,
        "n": len(qa),
        "recall@5": statistics.mean(recalls5),
        "recall@10": statistics.mean(recalls10),
        "MRR": statistics.mean(rrs),
        "misses": misses,
    }


def main() -> None:
    qa = [json.loads(l) for l in open("data/qa_dataset_raw.jsonl")]
    print(f"QA set: {len(qa)} questions")
    chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
    r = Retriever(chunks)

    results = []
    for mode in ["vector", "bm25", "hybrid"]:
        res = eval_mode(r, qa, mode)
        results.append(res)
        print(
            f"{mode:7s}  recall@5={res['recall@5']:.3f}  "
            f"recall@10={res['recall@10']:.3f}  MRR={res['MRR']:.3f}  "
            f"miss={len(res['misses'])}"
        )

    with open("data/eval_baseline.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("\nwritten data/eval_baseline.json")

    # 坏案例落盘（P2 弹药）
    hyb = results[-1]
    with open("data/miss_cases.txt", "w", encoding="utf-8") as f:
        for m in hyb["misses"]:
            f.write(m + "\n")
    print(f"miss cases -> data/miss_cases.txt")


if __name__ == "__main__":
    main()
