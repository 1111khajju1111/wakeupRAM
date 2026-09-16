# Multi-stage build: keeps the production image free of build toolchains
# (gcc etc. needed only to compile psycopg2-binary's transitive deps on some
# platforms) and pip's cache, so the shipped image is smaller and has a
# smaller attack surface than a single-stage `pip install` image.

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


FROM python:3.12-slim AS runtime

# libpq5 (the runtime lib) is needed even though libpq-dev (the headers,
# builder-stage only) is not — psycopg2 links against it at import time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 wakeupram

COPY --from=builder /install /usr/local
WORKDIR /app
COPY . .

# Never bake secrets into the image — DATABASE_URL, JWT_SECRET_KEY, and the
# AI/voice provider keys are all read from the environment at runtime (see
# app/core/config.py). Render, and the docker-compose.yml here, inject them
# as env vars, never as ARG/build-time values that would end up in image
# layers or `docker history`.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER wakeupram
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Migrations run before the server starts so a fresh deploy never serves
# traffic against a schema it doesn't match. If alembic fails, the
# container exits non-zero and Render/Docker report the deploy as failed
# rather than serving requests against a broken database.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
