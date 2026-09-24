"""配置加载：.env -> dataclass，全项目唯一配置入口。

设计要点：
  - 双栈可切换：LLM 与 Embedding 各自独立一组 base_url/key/model，
    默认智谱，改环境变量即可切 OpenAI / DeepSeek / Qwen。
  - API key 只进 .env（已 gitignore），代码与配置样例零密钥。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str


@dataclass(frozen=True)
class RetrievConfig:
    top_k: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 64
    rrf_k: int = 60  # Reciprocal Rank Fusion 常数，60 是论文默认值


@dataclass(frozen=True)
class StoreConfig:
    qdrant_path: Path = field(default_factory=lambda: Path("./data/qdrant"))
    collection: str = "manual_chunks"


@dataclass(frozen=True)
class Settings:
    llm: LLMConfig
    embed: LLMConfig
    retrieval: RetrievConfig = field(default_factory=RetrievConfig)
    store: StoreConfig = field(default_factory=StoreConfig)


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    llm = LLMConfig(
        base_url=os.environ.get("LLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
        api_key=os.environ.get("LLM_API_KEY", ""),
        model=os.environ.get("LLM_MODEL", "glm-4.7"),
    )
    embed = LLMConfig(
        base_url=os.environ.get("EMBED_BASE_URL", llm.base_url),
        api_key=os.environ.get("EMBED_API_KEY", llm.api_key),
        model=os.environ.get("EMBED_MODEL", "embedding-3"),
    )
    retrieval = RetrievConfig(
        top_k=int(os.environ.get("TOP_K", "5")),
        chunk_size=int(os.environ.get("CHUNK_SIZE", "512")),
        chunk_overlap=int(os.environ.get("CHUNK_OVERLAP", "64")),
    )
    store = StoreConfig(
        qdrant_path=Path(os.environ.get("QDRANT_PATH", "./data/qdrant")),
        collection=os.environ.get("COLLECTION", "manual_chunks"),
    )
    return Settings(llm=llm, embed=embed, retrieval=retrieval, store=store)
