# ─── Base stage ───
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

COPY . .

# ─── API target ───
FROM base AS api
EXPOSE 8000
CMD ["sh", "-c", "python init_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# ─── Worker target ───
FROM base AS worker
CMD ["sh", "-c", "python init_db.py && python -m app.worker"]
