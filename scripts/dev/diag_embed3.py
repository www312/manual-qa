"""诊断 3：8 条真实文本都失败但 2 条成功——按单条定位坏文本。"""

import json

from manual_qa.config import load_settings
from manual_qa.llm import EmbeddingClient

s = load_settings()
e = EmbeddingClient(s.embed)
texts = [json.loads(l)["text"] for l in open("data/chunks.jsonl")]

for i in range(8):
    try:
        e.embed([texts[i]])
        print(f"[{i}] OK  len={len(texts[i])}")
    except Exception as ex:
        print(f"[{i}] FAIL len={len(texts[i])} :: {texts[i][:120]!r}")
