"""继续诊断：二分定位触发 400 的批量规模/内容。"""

import json

from manual_qa.config import load_settings
from manual_qa.llm import EmbeddingClient

s = load_settings()
e = EmbeddingClient(s.embed)
texts = [json.loads(l)["text"] for l in open("data/chunks.jsonl")]

# 1) 真实 batch64
try:
    v = e.embed(texts[:64])
    print("real batch64 OK")
except Exception as ex:
    print("real batch64 FAIL:", str(ex)[:90])
    # 2) 二分规模
    for n in [32, 16, 8]:
        try:
            e.embed(texts[:n])
            print(f"batch{n} OK")
            break
        except Exception:
            print(f"batch{n} FAIL")
    # 3) 总字符数视角
    for n in [64, 32, 16]:
        chars = sum(len(t) for t in texts[:n])
        print(f"batch{n} total chars: {chars}")
