"""对话式改写（Contextualize）：把多轮追问改写成独立问题再检索。

设计（面试考点）：
  - 为什么不改检索器而改问题：检索器（BM25/向量）没有对话状态，
    与其在检索层注入历史（侵入式改动），不如在入口处把
    "那它的复位值呢" → "RCC_APB1LENR 的复位值是多少" 一次性归一化，
    下游（改写/hybrid/rerank/生成）全部无感知复用——单一职责。
  - 第 1 问零成本直通；带历史才触发 LLM 改写（1 次调用，~300 token）。
  - 改写失败/超时 → 原问题兜底，不阻塞主链路。
"""

from __future__ import annotations

from manual_qa.config import load_settings
from manual_qa.llm import LLMClient

CTX_PROMPT = """你是问题改写器。根据对话历史，把用户的最新追问改写成一个
不含代词、不依赖上下文、可独立理解的完整问题。

规则：
- 最新问题已经独立完整时，原样输出，不要改写
- 代词（它/这个/那个/上述）必须解析成具体对象（寄存器名/外设名/API名）
- 保留最新问题里的新信息（问复位值就保留"复位值"）
- 只输出改写后的问题本身，不要解释
- 无法确定指代对象时，原样输出最新问题（宁可不动也不要猜错）

对话历史：
{history}

最新问题：{question}

改写后的独立问题："""


class Contextualizer:
    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or LLMClient(load_settings().llm)

    def rewrite(
        self, question: str, history: list[dict[str, str]] | None = None
    ) -> str:
        """history: [{"q": "...", "a": "..."}] 最近 N 轮。空/None 时直通。"""
        if not history:
            return question
        # 只取最近 3 轮，答案截断防 token 膨胀
        recent = history[-3:]
        lines = []
        for i, turn in enumerate(recent, 1):
            a = turn.get("a", "")[:300]
            lines.append(f"第{i}轮问：{turn.get('q', '')}\n第{i}轮答：{a}")
        prompt = CTX_PROMPT.format(history="\n".join(lines), question=question)
        try:
            out = self.llm.chat(
                [{"role": "user", "content": prompt}], temperature=0.0
            ).strip().strip("\"'`")
            # 改写失败兜底：空输出或过长（变成了解释）时用原问题
            if not out or len(out) > len(question) * 4 + 40:
                return question
            return out
        except Exception:
            return question
