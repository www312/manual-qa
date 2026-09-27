"""MCP Server：把手册检索封装为 manual_search 工具，供外部 Agent 挂载。

用法（Claude Desktop / 任何 MCP 客户端）：
  {"mcpServers": {"manual-qa": {"command": "uv", "args": ["--directory",
   "<项目路径>", "run", "python", "-m", "manual_qa.mcp_server"]}}}

设计（面试考点）：
  - 工具粒度：只暴露 search 不暴露 ask——Agent 自己决定何时查、查什么、
    怎么综合；RAG 的"生成"交给宿主 LLM，这才是 tool 的正确姿势
  - 返回结构：chunk 列表带 chapter/page 元数据而非纯文本，让 Agent 能引用出处
"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

mcp = MCPServer("manual-qa")

_retriever = None


def _get_retriever():
    global _retriever
    if _retriever is None:
        from manual_qa.retrieval import Retriever

        chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
        _retriever = Retriever(chunks)
    return _retriever


@mcp.tool()
def manual_search(query: str, k: int = 5, mode: str = "hybrid") -> str:
    """检索 STM32H743 (RM0433) 与 ESP-IDF 技术手册。

    Args:
        query: 检索问题（中英文均可；寄存器名/API 名请原样保留）
        k: 返回条数 1-10，默认 5
        mode: vector | bm25 | hybrid（默认 hybrid，推荐）

    Returns:
        JSON 数组：[{n, chapter, page, doc, score, text}]，text 为原文块
    """
    k = max(1, min(10, int(k)))
    if mode not in ("vector", "bm25", "hybrid"):
        mode = "hybrid"
    r = _get_retriever()
    hits = r.search(query, k=k, mode=mode)
    out = [
        {
            "n": i + 1,
            "doc": h["doc"],
            "chapter": h["chapter"],
            "page": h["page"],
            "score": round(float(h["score"]), 4),
            "text": h["text"][:1500],
        }
        for i, h in enumerate(hits)
    ]
    return json.dumps(out, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()  # stdio 传输
