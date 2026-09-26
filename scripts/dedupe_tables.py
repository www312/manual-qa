"""修复：去重表格双捕获（同一表格 MD 出现在相邻块中两次）。

原因：get_text('blocks') 的表格区域 block + find_tables 的 bbox 替换
在部分页面同时命中，占位符替换后残留第二份。
策略：块内重复表格段（连续两段高相似）去重 + 相邻同章节同页的完全重复行删除。
"""

import json
import re

chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
n_before = len(chunks)

out = []
for c in chunks:
    t = c["text"]
    # 表格段按空行切分，重复段（完全一致）删除
    parts = t.split("\n\n")
    seen, kept = set(), []
    for p in parts:
        key = p.strip()
        if key and key in seen and key.count("|") > 3:  # 只对表格段去重
            continue
        if key:
            seen.add(key)
        kept.append(p)
    c["text"] = "\n\n".join(kept)
    # 整块为空则丢
    if c["text"].strip():
        out.append(c)

# 相邻完全重复块（同doc+chapter+page+text）去重
final = []
for c in out:
    if final and final[-1]["doc"] == c["doc"] and final[-1]["text"] == c["text"]:
        continue
    final.append(c)

print(f"{n_before} -> {len(final)} chunks (removed {n_before - len(final)})")
with open("data/chunks_selected.jsonl", "w", encoding="utf-8") as f:
    for c in final:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print("rewritten")
