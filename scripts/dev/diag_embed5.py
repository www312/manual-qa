"""诊断 5：精确找出长度阈值（好文本 padding 复测，避开内容差异）。"""

from manual_qa.config import load_settings
from manual_qa.llm import EmbeddingClient

s = load_settings()
e = EmbeddingClient(s.embed)

import json

texts = [json.loads(l)["text"] for l in open("data/chunks.jsonl")]
bad = texts[3]
lo, hi = 6000, 7098  # 6000 OK, 7098 FAIL
while lo < hi - 1:
    mid = (lo + hi) // 2
    try:
        e.embed([bad[:mid]])
        lo = mid
    except Exception:
        hi = mid
print(f"阈值: {lo} chars OK, {hi} chars FAIL")
# 用另一条好文本验证
good = (texts[0] * 3)[: hi + 50]
try:
    e.embed([good])
    print(f"good {len(good)}: OK —— 阈值仅对该文本成立?")
except Exception:
    print(f"good {len(good)}: FAIL —— 全局长度阈值确认")
