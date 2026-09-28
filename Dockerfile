FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 依赖与源码分两步：uv_build 后端要求构建本包时 src 已存在
COPY pyproject.toml uv.lock ./
RUN mkdir -p src/manual_qa && echo "" > src/manual_qa/__init__.py \
 && uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY scripts ./scripts
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["uv", "run", "--no-sync", "uvicorn", "manual_qa.server:app", "--host", "0.0.0.0", "--port", "8000"]
