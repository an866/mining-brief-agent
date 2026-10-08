# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    MINING_BRIEF_HOME=/app

WORKDIR /app

# Install dependencies from the project metadata first so code edits do not
# invalidate the pip layer. The [llm] extra brings in `anthropic`; without an
# API key the agent simply uses its deterministic template narrator.
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/
RUN pip install ".[llm]"

# Runtime data (demo snapshots + sample PDFs) and convenience files.
COPY data/ data/
COPY scripts/ scripts/
COPY mcp-config.json docker-compose.yml RUN.md ./

# Default: run the exact query from the interview brief.
ENTRYPOINT ["mining-brief"]
CMD ["给我生成一份关于 Pilbara 锂矿的今日简报"]
