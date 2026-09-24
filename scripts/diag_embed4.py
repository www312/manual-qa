"""诊断 4：长度假设验证——把 FAIL 的文本截短再试。"""

from manual_qa.config import load_settings
from manual_qa.llm import EmbeddingClient

s = load_settings()
e = EmbeddingClient(s.embed)

import json

texts = [json.loads(l)["text"] for l in open("data/chunks.jsonl")]
bad = texts[3]
for cut in [6000, 5000, 4000, 3072]:
    try:
        e.embed([bad[:cut]])
        print(f"cut {cut}: OK")
    except Exception:
        print(f"cut {cut}: FAIL")
# 也检查是否内容问题：同样长度的正常文本
good = texts[0]
try:
    e.embed([good[: len(bad)]])
    print(f"good text padded to {len(bad)}: OK (说明是长度阈值而非内容)")
except Exception:
    print("good text same len FAIL (内容相关)")
