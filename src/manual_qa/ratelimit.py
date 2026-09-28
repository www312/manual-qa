"""部署用限流中间件：每 IP 每日 N 次问答（公开 demo 防刷 key）。

设计：
  - 内存计数（单进程 uvicorn 足够；多 worker 需换 Redis）
  - /health 与 /api/search 不限（search 无 LLM 调用，成本为零）
  - 超限返回 429 + 明确文案，前端 error 分支已能展示
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Request
from fastapi.responses import JSONResponse

DAILY_LIMIT = 30  # 每 IP 每日问答次数


class RateLimiter:
    def __init__(self, limit: int = DAILY_LIMIT) -> None:
        self.limit = limit
        self.counts: dict[str, list[int]] = defaultdict(list)

    def _prune(self, key: str, now: float) -> None:
        day_start = now - (now % 86400)
        self.counts[key] = [t for t in self.counts[key] if t > day_start]

    def allow(self, key: str) -> bool:
        now = time.time()
        self._prune(key, now)
        if len(self.counts[key]) >= self.limit:
            return False
        self.counts[key].append(now)
        return True

    def remaining(self, key: str) -> int:
        self._prune(key, time.time())
        return max(0, self.limit - len(self.counts[key]))


limiter = RateLimiter()


async def rate_limit_ask(request: Request, call_next):
    path = request.url.path
    if path == "/api/ask":
        ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
            request.client.host if request.client else "unknown"
        )
        if not limiter.allow(f"ask:{ip}"):
            return JSONResponse(
                status_code=429,
                content={"message": f"今日 {DAILY_LIMIT} 次提问额度已用完，明天再来吧～（学生 demo 限流防刷）"},
            )
    return await call_next(request)
