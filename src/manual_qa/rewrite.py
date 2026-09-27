"""查询改写：中文问句 → 英文检索词（补 BM25 跨语言短板）。

设计：glm-4.7 一次调用把问题翻译成"寄存器名+关键英文词"组成的
检索查询。缓存所有改写结果（评测期间同一问题只翻译一次）。
"""

from __future__ import annotations

import json
from pathlib import Path

from manual_qa.config import load_settings
from manual_qa.llm import LLMClient

PROMPT = """把下面的中文技术问题改写成英文检索查询，用于在英文芯片手册中做关键词检索。

规则：
- 输出只含检索关键词（寄存器名/信号名/外设名/技术名词），不要句子
- 保留所有专有名（如 HSEM、RCC_APB1ENR、Light-sleep）原样
- 用户连写的芯片名+外设名必须拆开：STM32GPIO 应拆为 STM32 GPIO
- 最多 10 个词，空格分隔
- 问题已是英文则原样输出（略作规范化）

问题：{q}

检索查询："""

_CACHE_PATH = Path("data/query_rewrites.json")


class QueryRewriter:
    def __init__(self) -> None:
        s = load_settings()
        self.llm = LLMClient(s.llm)
        self.cache: dict[str, str] = {}
        if _CACHE_PATH.exists():
            self.cache = json.loads(_CACHE_PATH.read_text())

    def rewrite(self, question: str) -> str:
        if question in self.cache:
            return self.cache[question]
        out = self.llm.chat(
            [{"role": "user", "content": PROMPT.format(q=question)}], temperature=0.0
        ).strip()
        # 容错：模型偶尔加引号/句号
        out = out.strip("\"'`").rstrip(".")
        self.cache[question] = out
        _CACHE_PATH.write_text(json.dumps(self.cache, ensure_ascii=False, indent=1))
        return out
