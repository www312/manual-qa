"""诊断：为什么 "STM32GPIO 有多少个引脚" 检索到 ESP32 文档。"""

import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import _tokenize
from manual_qa.rewrite import QueryRewriter

q = "STM32GPIO 有多少个引脚"
print("1. 保形分词结果:", _tokenize(q, drop_stop=True))

rw = QueryRewriter()
print("2. LLM 改写结果:", rw.rewrite(q))

# 关键：STM32GPIO 是连续 ASCII 串 → 保形分词切成一整个 token "stm32gpio"
# 这个词在 RM0433（只自称 STM32H743/GPIO）里几乎不存在！
# 但在 ESP-IDF 的 "芯片系列对比" 章节里 STM32 字样会出现
import json

chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
hits_rm = [c for c in chunks if c["doc"] == "rm0433" and "stm32gpio" in c["text"].lower()]
hits_esp = [c for c in chunks if c["doc"] == "espidf" and "stm32" in c["text"].lower()]
print(f"3. 'stm32gpio' 整词在 RM0433 语料中出现: {len(hits_rm)} 块")
print(f"   'stm32' 在 ESP-IDF 语料中出现: {len(hits_esp)} 块")
if hits_esp:
    print("   ESP-IDF 命中示例:", hits_esp[0]["chapter"][:40], "p", hits_esp[0]["page"])
