"""诊断智谱 embedding 400：单条/批量/长文本逐一排除。"""

import json

from manual_qa.config import load_settings
from manual_qa.llm import EmbeddingClient

s = load_settings()
e = EmbeddingClient(s.embed)
texts = [json.loads(l)["text"] for l in open("data/chunks.jsonl")]

v = e.embed([texts[0]])
print("single OK dim", len(v[0]))

short = ["测试" + str(i) for i in range(64)]
try:
    v = e.embed(short)
    print("batch64 short OK", len(v))
except Exception as ex:
    print("batch64 short FAIL", str(ex)[:80])

try:
    v = e.embed([texts[0], texts[1]])
    print("batch2 long OK", len(v))
except Exception as ex:
    print("batch2 long FAIL", str(ex)[:80])
