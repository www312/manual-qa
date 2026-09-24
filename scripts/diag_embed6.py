"""诊断 6：阈值疑似按 token 计。用 tiktoken 近似验证 8192 token 假设。"""

import json

import tiktoken

texts = [json.loads(l)["text"] for l in open("data/chunks.jsonl")]
enc = tiktoken.get_encoding("cl100k_base")

for i in [0, 3, 6, 7]:
    t = texts[i]
    n = len(enc.encode(t))
    print(f"[{i}] chars={len(t)} tokens~{n}")
