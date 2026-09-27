"""RAG 生成层：检索增强 + 引用溯源 + SSE 流式。

Prompt 设计（面试考点）：
  - 每个检索块带编号 [1]..[k] 和出处（文档/章节/页码），
    要求答案内联标注 [n] —— 引用可验证是 RAG 防幻觉的底线。
  - 明确「只依据资料」指令 + 「资料不足时直说」——宁缺毋假。
"""

from __future__ import annotations

from collections.abc import Iterator

from openai.types.chat import ChatCompletionMessageParam

from manual_qa.config import load_settings
from manual_qa.llm import LLMClient

SYSTEM = """你是嵌入式技术手册专家助手。严格依据下面编号资料回答问题：
- 答案中引用资料处标注 [编号]，如"APB1 时钟使能寄存器地址偏移为 0x58 [2]"
- 资料含答案或答案的一部分时：回答能答的部分
- 资料与问题同主题但不含答案（如问到具体数值/参数而资料只有概述）：
  先明确说明"资料中未给出 XX 的直接答案"，再简要说明资料中与之最相关的
  内容是什么（标注引用），并提示用户该信息可能需要查阅手册哪一部分
- 完全无关的问题：直接说明"资料中未找到相关内容"
- 禁止编造寄存器地址、位定义、数值参数
- 用中文回答（资料为英文时翻译关键术语，保留寄存器/配置名原文）
- 简洁：先直接答案，再补充必要上下文"""


def build_context(hits: list[dict]) -> str:
    parts = []
    for i, h in enumerate(hits, 1):
        src = f"{h['doc']} | {h['chapter']} | p{h['page']}"
        parts.append(f"[{i}] ({src})\n{h['text']}")
    return "\n\n".join(parts)


class RAG:
    def __init__(self, retriever, llm: LLMClient | None = None):
        self.r = retriever
        self.llm = llm or LLMClient(load_settings().llm)

    def _messages(self, question: str, hits: list[dict]) -> list[ChatCompletionMessageParam]:
        return [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"资料：\n{build_context(hits)}\n\n问题：{question}",
            },
        ]

    async def astream(self, question: str, hits: list[dict]):
        """异步流式生成（FastAPI SSE 用）。"""
        import asyncio

        for delta in self.llm.stream(self._messages(question, hits)):
            await asyncio.sleep(0)  # 让出事件循环，SSE 心跳可穿插
            yield delta

    def ask(self, question: str, k: int = 5, mode: str = "hybrid") -> dict:
        hits = self.r.search(question, k=k, mode=mode)
        answer = self.llm.chat(self._messages(question, hits))
        return {"question": question, "answer": answer, "citations": hits}

    def ask_stream(self, question: str, k: int = 5, mode: str = "hybrid"):
        hits = self.r.search(question, k=k, mode=mode)
        yield {"event": "citations", "data": hits}

        def gen() -> Iterator[str]:
            yield from self.llm.stream(self._messages(question, hits))

        yield {"event": "answer", "data": gen()}
