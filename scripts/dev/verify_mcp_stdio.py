"""通过 stdio JSON-RPC 完整验证 MCP server（模拟 Claude 等客户端挂载）。"""

import json
import subprocess
import sys

proc = subprocess.Popen(
    [sys.executable, "-m", "manual_qa.mcp_server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
    text=True,
    cwd="/Users/wengzitao/manual-qa",
)


def send(msg: dict) -> None:
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def recv() -> dict | None:
    line = proc.stdout.readline()
    return json.loads(line) if line.strip() else None


send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2025-06-18",
                 "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}}})
init = recv()
print("init ok:", bool(init))

send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
tools = recv()
names = [t["name"] for t in tools["result"]["tools"]] if tools and "result" in tools else tools
print("tools:", names)

send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
      "params": {"name": "manual_search",
                 "arguments": {"query": "GPIO pull-up configuration", "k": 2}}})
result = recv()
if result and "result" in result:
    content = result["result"].get("content", [])
    text = content[0]["text"] if content else ""
    arr = json.loads(text)
    for h in arr:
        print(f"  [{h['n']}] {h['chapter'][:50]} p{h['page']}")
    print("stdio MCP round-trip OK")
else:
    print("result:", str(result)[:300])

proc.terminate()
