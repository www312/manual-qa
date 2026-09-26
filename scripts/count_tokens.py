"""精确核算 embedding 已消耗 token 与断点位置。"""

import json

import tiktoken

enc = tiktoken.get_encoding("cl100k_base")
total = 0
n = 0
# 入库顺序 = 文件行序；embed 顺序同步（batch 32 顺序调用）
# 智谱免费/资源包额度通常按 token 计，与 cl100k 有 ~±10% 偏差，取区间表述
batch_done = 0
for i, line in enumerate(open("data/chunks.jsonl")):
    c = json.loads(line)
    n += 1
    total += len(enc.encode(c["text"]))

print(f"chunks: {n}")
print(f"总 token(cl100k 口径): {total:,}")
print(f"智谱实际计费口径估计: {int(total*0.9):,} ~ {int(total*1.1):,}")
print(f"第一批 429 前已成功批次数(日志推算): 见下")
