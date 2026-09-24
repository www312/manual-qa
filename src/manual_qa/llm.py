"""双栈 LLM 客户端：OpenAI 兼容协议，智谱为默认后端。

为什么这么设计（面试考点）：
  智谱 / DeepSeek / Qwen / OpenAI 全部兼容 OpenAI Chat Completions 协议，
  所以只写一个客户端、换 base_url+key+model 三元组即可跨厂商迁移。
  这与 atm-forward 的网关封装思路同构：协议归一，供应商可插拔。
"""

from __future__ import annotations

from collections.abc import Iterator

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from manual_qa.config import LLMConfig


class LLMClient:
    """Chat 客户端：sync 一次问答 + stream 流式（SSE 用）。"""

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    def chat(self, messages: list[ChatCompletionMessageParam], temperature: float = 0.1) -> str:
        resp = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    def stream(self, messages: list[ChatCompletionMessageParam], temperature: float = 0.1) -> Iterator[str]:
        stream = self.client.chat.completions.create(
            model=self.cfg.model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class EmbeddingClient:
    """Embedding 客户端：带简单重试，批量上限 64（智谱限制）。"""

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        batch = 64
        for i in range(0, len(texts), batch):
            part = texts[i : i + batch]
            for attempt in range(3):
                try:
                    resp = self.client.embeddings.create(
                        model=self.cfg.model, input=part
                    )
                    out.extend(d.embedding for d in resp.data)
                    break
                except Exception:
                    if attempt == 2:
                        raise
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]
