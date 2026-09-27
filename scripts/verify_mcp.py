"""MCP server 冒烟：列出工具 + 真实调用 manual_search。"""

import asyncio

import sys

sys.path.insert(0, "src")


async def main() -> None:
    from manual_qa.mcp_server import mcp, manual_search

    tools = await mcp.list_tools()
    print("registered:", [t.name for t in tools])

    out = manual_search("HSEM ICR register offset", k=3)
    import json

    arr = json.loads(out)
    for h in arr:
        print(f"[{h['n']}] {h['chapter'][:55]} p{h['page']} score={h['score']}")


asyncio.run(main())
