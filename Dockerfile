# ===================================================================
# Server Agent vNext: Dockerfile
# ===================================================================
# Multi-stage build for autonomous AGI agent FastAPI application
# Base: Python 3.11 slim for minimal image size

# === Stage 1: Builder ===
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-vnext.txt .

# Create wheels for faster installation in final stage
RUN pip install --user --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --user --no-cache-dir -r requirements-vnext.txt


# === Stage 2: Runtime ===
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies including Node.js for Claude CLI, procps for ps command, and SSH client for host access
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    ca-certificates \
    gnupg \
    procps \
    openssh-client \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && NODE_MAJOR=20 && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Note: Claude CLI will be mounted from host via docker run -v /usr/bin/claude:/usr/local/bin/claude

# Create non-root user for security (before copying packages)
RUN useradd -m -u 1000 agent && \
    mkdir -p /app/logs /app/data /home/agent/.claude && \
    chown -R agent:agent /app /home/agent/.claude

# Copy Python packages from builder to agent user's home
COPY --from=builder --chown=agent:agent /root/.local /home/agent/.local

# Set PATH to use installed packages from agent's home
ENV PATH=/home/agent/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Copy application code
COPY --chown=agent:agent app/ ./app/

# Copy entrypoint script
COPY --chown=agent:agent docker-entrypoint.sh /home/agent/docker-entrypoint.sh
RUN chmod +x /home/agent/docker-entrypoint.sh

# Switch to non-root user
USER agent

# Set entrypoint
ENTRYPOINT ["/home/agent/docker-entrypoint.sh"]

# Expose application port
EXPOSE 8000

# Health check (Docker will use this to determine if container is running)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: run FastAPI with uvicorn (no --reload to prevent restarts during Claude Code execution)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Production command (use this for production deployment)
# CMD ["uvicorn", "app.main:app", \
#      "--host", "0.0.0.0", \
#      "--port", "8000", \
#      "--workers", "4", \
#      "--loop", "uvloop", \
#      "--access-log"]
