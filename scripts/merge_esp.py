"""补 ESP-IDF 全量（2.5M token）进精选集：48M + 2.5M = 50.5M ≈ 25.3 元，30 元预算内。"""

import json

kept = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
esp = [json.loads(l) for l in open("data/chunks.jsonl") if json.loads(l)["doc"] == "espidf"]
allc = kept + esp
with open("data/chunks_selected.jsonl", "w", encoding="utf-8") as f:
    for c in allc:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
docs = {}
for c in allc:
    docs[c["doc"]] = docs.get(c["doc"], 0) + 1
print(f"final: {len(allc)} chunks", docs)
