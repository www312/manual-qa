"""精选子集入库：RM0433 寄存器/功能章节优先 + ESP-IDF 全量。

30 元预算 → 上限约 55M token（留 P1 评测余量取 ~48M）。
策略：按章节价值排序，取高价值章节直至预算上限。
简历口径从"21.7万块"调整为"高价值精选 N 万块"——精选语料本来就是更工程化的故事。
"""

import json

import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

chunks = [json.loads(l) for l in open("data/chunks.jsonl")]

# 章节价值分级（人工规则，可解释）：
# P0 保留：寄存器描述、外设功能、配置参考 —— 问答密度最高的部分
KEEP_RM = (
    "register", "Register", "functional overview", "Functional",
    "description", "Description", "configuration", "Configuration",
    "low-power", "Low-power", "clock", "Clock", "GPIO", "interrupt", "Interrupt",
    "DMA", "timer", "Timer", "UART", "SPI", "I2C", "ADC", "DAC",
)
# 丢弃：目录、修订记录、封底、纯表格附录编号页
DROP_RM = ("Contents", "Revision history", "revised", "Table of contents")

kept, dropped = [], 0
tok = 0
BUDGET = 48_000_000

for c in chunks:
    ch = c["chapter"]
    if c["doc"] == "espidf":
        keep = True  # 中文语料全保留（量大但占比小）
    else:
        if any(d in ch for d in DROP_RM):
            dropped += 1
            continue
        keep = any(k in ch for k in KEEP_RM)
    if not keep:
        dropped += 1
        continue
    t = len(enc.encode(c["text"]))
    if tok + t > BUDGET:
        break
    kept.append(c)
    tok += t

print(f"kept {len(kept)} chunks, {tok/1e6:.1f}M tokens, dropped {dropped}")
docs = {}
for c in kept:
    docs[c["doc"]] = docs.get(c["doc"], 0) + 1
print(docs)

with open("data/chunks_selected.jsonl", "w", encoding="utf-8") as f:
    for c in kept:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print("written data/chunks_selected.jsonl")
