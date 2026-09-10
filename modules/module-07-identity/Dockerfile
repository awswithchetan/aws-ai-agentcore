# Aria — ShopSmart AI Customer Support Agent
# Module 07: Identity — adds identity/ directory for JWT claim extraction
# Multi-stage build for a lean production image.

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

RUN useradd --create-home --shell /bin/bash aria
WORKDIR /app

COPY --from=builder /install /usr/local

# Copy agent source — Module 07 adds identity/ for JWT claim extraction
COPY --chown=aria:aria agent.py .
COPY --chown=aria:aria config.py .
COPY --chown=aria:aria tools/    tools/
COPY --chown=aria:aria memory/   memory/
COPY --chown=aria:aria identity/ identity/

USER aria

EXPOSE 8080

CMD ["python", "agent.py"]
