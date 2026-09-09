# Aria — ShopSmart AI Customer Support Agent
# Multi-stage build for a lean production image.
# Framework-agnostic: swap requirements.txt and agent.py to use
# LangChain, CrewAI, or any other framework without changing this file.

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install pip dependencies into an isolated prefix so we can copy them cleanly
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Non-root user for security best practice
RUN useradd --create-home --shell /bin/bash aria
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy agent source
COPY --chown=aria:aria agent.py .
COPY --chown=aria:aria tools/    tools/
COPY --chown=aria:aria policies/ policies/

USER aria

# AgentCore Runtime expects the app to listen on port 8080
EXPOSE 8080

# Entry point — BedrockAgentCoreApp.run() starts the HTTP server
CMD ["python", "agent.py"]
