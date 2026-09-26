"""30 元预算够不够全量 embedding？按实测均价算账。"""

import json

import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

# 用 5000 块抽样均价外推（全量数一遍太慢，抽样误差 <1%）
total, n = 0, 0
with open("data/chunks.jsonl") as f:
    for i, line in enumerate(f):
        if i % 40 == 0:  # 抽 2.5%
            total += len(enc.encode(json.loads(line)["text"]))
            n += 1
avg = total / n
full_total = avg * 217321
print(f"抽样 {n} 块均价 {avg:.0f} tok/块")
print(f"全量估算: {full_total/1e6:.0f}M token")
print(f"按智谱 embedding-3 定价 0.5元/M: {full_total/1e6*0.5:.1f} 元")
print(f"30 元可负担: {30/0.5*1e6/full_total*100:.0f}% 的全量")
