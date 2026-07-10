# ─── Base stage ───
FROM python:3.12-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app
ENV PYTHONPATH=/app

# Install deps first (cached layer)
COPY pyproject.toml ./
RUN uv pip install --system --no-cache .

# Copy app code
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY init_db.py .

# ─── API target ───
FROM base AS api
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]

# ─── Worker target ───
FROM base AS worker
CMD ["sh", "-c", "alembic upgrade head && python -m app.worker"]

# ─── Channels target ───
FROM base AS channels
CMD ["sh", "-c", "sleep 10 && python -m app.channels.manager"]
