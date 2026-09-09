# Aria — ShopSmart AI Customer Support Agent
# Module 06: Memory — adds memory/ directory for persistent customer memory
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

# Copy agent source — Module 06 adds memory/ for AgentCore Memory integration
COPY --chown=aria:aria agent.py .
COPY --chown=aria:aria config.py .
COPY --chown=aria:aria tools/    tools/
COPY --chown=aria:aria policies/ policies/
COPY --chown=aria:aria memory/   memory/

USER aria

EXPOSE 8080

CMD ["python", "agent.py"]
