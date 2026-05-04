# Dockerfile for the Flowgraph backend.
# Notes:
#   - Runs as non-root (UID 1001).
#   - The non-root user joins the `docker` group so it can talk to the
#     bind-mounted /var/run/docker.sock. The DOCKER_GID build arg must match
#     the host's docker group GID (compose file passes it from the host).
FROM python:3.11-slim

WORKDIR /app

# System deps. --no-install-recommends keeps the image lean and reduces the
# attack surface (closes trivy DS-0029).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user. UID 1001 to avoid colliding with stock node:slim's `node`
# user (1000) — relevant when both images are on the same docker host.
ARG DOCKER_GID=999
RUN groupadd -r flowgraph \
 && useradd -r -g flowgraph -u 1001 -m -d /home/flowgraph flowgraph \
 && (groupmod -g ${DOCKER_GID} docker 2>/dev/null \
     || groupadd -g ${DOCKER_GID} docker) \
 && usermod -aG docker flowgraph

# Install Python deps as root (writes into /usr/local/lib/...).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-bake the default embedding model (issue14) so first /api/embed call
# is instant instead of 3-5s on cold start. The cache lives at /opt/hf-cache
# (NOT /app/* because compose bind-mounts ../server:/app at runtime, which
# would shadow anything baked under /app).
ENV HF_HOME=/opt/hf-cache
RUN mkdir -p /opt/hf-cache \
 && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')" \
 && chown -R flowgraph:flowgraph /opt/hf-cache

# Pre-create runtime dirs with the right ownership.
RUN mkdir -p /app/workspaces /app/cache /app/storage /app/data \
 && chown -R flowgraph:flowgraph /app

# Copy application with proper ownership in one shot.
COPY --chown=flowgraph:flowgraph . .

# Move the entrypoint to /entrypoint.sh so it survives a volume-mounted /app.
RUN mv /app/setup/entrypoint.sh /entrypoint.sh \
 && chmod +x /entrypoint.sh \
 && chown flowgraph:flowgraph /entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

USER flowgraph
ENTRYPOINT ["/entrypoint.sh"]
