# BatchHelm API container.
# Built for Alibaba Cloud Container Service (ACK) / Elastic Compute Service (ECS).
# Build context is the repository root so the API can read the shared README.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    APP_ENV=production \
    LOG_LEVEL=info \
    DATABASE_PATH=/data/batchhelm.db \
    MEMORY_PATH=/data/batchhelm-memory.db \
    ORCHESTRATION_DATABASE_PATH=/data/orchestration.db \
    INTAKE_DATABASE_PATH=/data/intake.db \
    QWEN_PROOF_DATABASE_PATH=/data/qwen-proof.db \
    UPLOAD_DIR=/data/uploads

WORKDIR /app

# README is referenced by the API package metadata (pyproject readme path).
COPY README.md ./README.md
COPY services/api ./services/api

WORKDIR /app/services/api
RUN uv sync --frozen --no-dev

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8000

# Qwen credentials are injected at runtime (never baked into the image).
CMD ["uv", "run", "uvicorn", "batchhelm_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
