"""Agent 模式：LLM 自主决定何时调用 manual_search 工具的 ReAct 循环。

设计（面试考点）：
  - 这不是 MCP server 的替代，而是"宿主 Agent"侧：LLM 通过 OpenAI function
    calling 协议声明工具 → 模型自己决定查不查、查什么、何时停
  - 与普通 RAG 的区别：普通模式 = 无条件检索后生成；Agent 模式 = 检索是
    模型的"手"，闲聊/常识问题不查，专业问题可能连续多次查询再综合
  - 事件流：step（工具调用过程可视化）+ delta（最终答案流式）
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any, cast

from openai.types.chat import ChatCompletionMessageParam, ChatCompletionToolParam

from manual_qa.config import load_settings
from manual_qa.llm import LLMClient

SYSTEM = """你是嵌入式技术专家助手，可以调用 manual_search 工具查询
STM32H743 (RM0433) 与 ESP-IDF 官方手册。

策略：
- 涉及芯片寄存器/外设/驱动/API 细节的问题：先查手册再答，引用处标注 [n]
- 闲聊、常识、与你已给出的内容相关的追问：直接回答，不要浪费查询
- 查询词用英文技术名词（寄存器名原样保留），一次可以多个查询
- 资料不足时明说，禁止编造寄存器地址或位定义"""

TOOLS: list[ChatCompletionToolParam] = [
    {
        "type": "function",
        "function": {
            "name": "manual_search",
            "description": "检索 STM32H743 (RM0433) 与 ESP-IDF 技术手册，返回带章节/页码的原文块",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "英文检索词，寄存器名/API 名原样保留",
                    },
                },
                "required": ["query"],
            },
        },
    }
]


class AgentRAG:
    def __init__(self, retriever, max_steps: int = 4):
        self.r = retriever
        self.llm = LLMClient(load_settings().llm)
        self.max_steps = max_steps

    async def run(self, question: str) -> AsyncIterator[dict]:
        """产出三类事件：{type:'step',...} {type:'delta',text} {type:'done',...}"""
        import asyncio

        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": question},
        ]
        cites: list[dict] = []

        for step in range(self.max_steps):
            resp = await asyncio.to_thread(
                self.llm.client.chat.completions.create,
                model=self.llm.cfg.model,
                messages=messages,
                tools=TOOLS,
                temperature=0.1,
            )
            msg = resp.choices[0].message

            if not msg.tool_calls:
                # 模型认为可以作答（或不需要工具）
                yield {"type": "step", "kind": "answer", "text": msg.content or ""}
                yield {"type": "done", "citations": cites}
                return

            messages.append(msg)  # type: ignore[arg-type]
            for tc in msg.tool_calls or []:
                fn = getattr(tc, "function", None)
                if fn is None or fn.name != "manual_search":
                    continue
                args = json.loads(fn.arguments or "{}")
                query = str(args.get("query", ""))[:200]
                yield {"type": "step", "kind": "search", "query": query}

                hits = await asyncio.to_thread(
                    self.r.search, query, 5, "hybrid"
                )
                for h in hits:
                    if h["chunk_id"] not in {c["chunk_id"] for c in cites}:
                        cites.append(h)

                tool_out = json.dumps(
                    [
                        {
                            "n": i + 1,
                            "chapter": h["chapter"],
                            "page": h["page"],
                            "text": h["text"][:1200],
                        }
                        for i, h in enumerate(hits)
                    ],
                    ensure_ascii=False,
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_out,
                    }  # type: ignore[arg-type]
                )

        # 步数用尽，强制收尾（不带 tools 再问一次）
        resp = await asyncio.to_thread(
            self.llm.client.chat.completions.create,
            model=self.llm.cfg.model,
            messages=messages,
            temperature=0.1,
        )
        yield {"type": "step", "kind": "answer", "text": resp.choices[0].message.content or ""}
        yield {"type": "done", "citations": cites}
