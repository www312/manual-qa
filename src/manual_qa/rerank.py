"""LLM 重排（rerank）：对混合检索 top-N 做 listwise 精排，解决近邻干扰。

设计（面试考点）：
  - 为什么重排能解决 APB1ENR/LPENR 混淆：召回阶段（BM25+向量）看的是
    表面相似度，"RCC_APB1LLPENR" 和 "RCC_APB1ENR" 字面/语义都极近；
    listwise 重排让 LLM 逐块对照问题判断"这块是否直接回答问题"，
    能理解 L=Low-power 修饰导致的语义差异——这是字面匹配做不到的。
  - 粗排→精排两段式是检索系统标准架构（召回快而糙，精排慢而准），
    只对 top-10 重排，成本 = 每问 1 次 LLM 调用（~2K token）。
  - 顺序保持稳定：重排失败（异常/超时）自动回退原序，不阻塞主链路。
"""

from __future__ import annotations

import json

from manual_qa.config import load_settings
from manual_qa.llm import LLMClient

RERANK_PROMPT = """你是嵌入式手册检索结果的重排器。用户问题和候选文档块如下，
请按"直接回答问题的程度"从高到低重新排列。

判断标准：
- 块中包含问题所问的寄存器/参数的直接定义、地址、位描述 → 排最前
- 块的主题相关但是不同变体（如问 APB1ENR 而块是 APB1LPENR 低功耗版本、
  APB1HENR 高位版本）→ 视问题而定：若问题用的旧名，提供拆分后寄存器的块排前；
  纯邻近变体排后
- 仅概述/目录/相邻章节 → 排最后

问题：{question}

候选块：
{blocks}

严格输出 JSON 数组（仅编号，按新顺序，如 [3,1,4,2,5]），不要其他内容。"""


class Reranker:
    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient(load_settings().llm)

    def rerank(self, question: str, hits: list[dict], top_n: int = 5) -> list[dict]:
        """对 hits 重排，返回前 top_n。失败时原样返回前 top_n（降级保命）。"""
        if len(hits) <= 1:
            return hits
        blocks = []
        for i, h in enumerate(hits, 1):
            text = h["text"][:500]  # 控制上下文长度
            blocks.append(f"[{i}] ({h['chapter'][:60]} | p{h['page']})\n{text}")
        prompt = RERANK_PROMPT.format(
            question=question, blocks="\n\n".join(blocks)
        )
        try:
            raw = self.llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.0
            ).strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            order = json.loads(raw)
            # 校验：必须是 1..len(hits) 的排列（允许部分）
            valid = [i for i in order if isinstance(i, int) and 1 <= i <= len(hits)]
            if not valid:
                return hits[:top_n]
            seen: set[int] = set()
            ranked: list[dict] = []
            for i in valid:
                if i not in seen:
                    ranked.append(hits[i - 1])
                    seen.add(i)
            # 未被排到的块追加在尾部（防丢块）
            for i, h in enumerate(hits, 1):
                if i not in seen:
                    ranked.append(h)
            return ranked[:top_n]
        except Exception:
            return hits[:top_n]
