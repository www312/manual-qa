"""连通性冒烟测试：验证智谱 chat / embedding / 流式三条链路真实可用。

运行：uv run pytest tests/test_smoke.py -v
标记为 slow（真实 API 调用），平时 pytest 默认不跑：
  uv run pytest -m "not slow"        # 单元测试
  uv run pytest -m slow              # 冒烟（打真实 API）
"""

import os

import pytest

from manual_qa.config import load_settings
from manual_qa.llm import EmbeddingClient, LLMClient

pytestmark = pytest.mark.slow

_settings = load_settings()
HAS_KEY = bool(_settings.llm.api_key and "your-" not in _settings.llm.api_key)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not HAS_KEY, reason=".env 未配置真实 API key"),
]


def test_chat() -> None:
    llm = LLMClient(_settings.llm)
    answer = llm.chat([{"role": "user", "content": "回复两个字：可用"}])
    assert isinstance(answer, str) and len(answer) > 0
    print(f"\n[chat] model={_settings.llm.model} -> {answer!r}")


def test_stream() -> None:
    llm = LLMClient(_settings.llm)
    chunks = list(llm.stream([{"role": "user", "content": "从 1 数到 5，空格分隔"}]))
    assert len(chunks) >= 2, "流式应返回多个增量片段"
    print(f"\n[stream] {len(chunks)} chunks: {''.join(chunks)!r}")


def test_embedding() -> None:
    emb = EmbeddingClient(_settings.embed)
    vec = emb.embed_query("寄存器地址配置方法")
    assert len(vec) == 2048, f"智谱 embedding-3 应返回 2048 维，实际 {len(vec)}"
    print(f"\n[embedding] model={_settings.embed.model} dim={len(vec)}")


if __name__ == "__main__":
    os.environ.setdefault("PYTEST_ADDOPTS", "-m slow -v -s")
    raise SystemExit(pytest.main([__file__]))
