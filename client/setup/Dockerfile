# Dockerfile for the Flowgraph frontend (Vite dev or production build).
# Runs as the stock `node` user (UID 1000) — non-root.

FROM node:20-alpine

WORKDIR /app

# wget for healthcheck (Alpine doesn't ship it).
RUN apk add --no-cache wget

# Make /app writable by the node user before install (yarn writes node_modules).
RUN chown -R node:node /app

# Switch to non-root for installs and runtime. Lock files are owned by node;
# permissions stay clean across volume-mounts in dev mode.
USER node

COPY --chown=node:node package.json yarn.lock* ./
RUN yarn install

COPY --chown=node:node . .

EXPOSE 5173 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:5173/ || exit 1

# Re-install deps if package.json is newer than node_modules (volume-mount aware).
USER root
RUN echo '#!/bin/sh' > /entrypoint.sh && \
    echo 'if [ ! -d "node_modules" ] || [ "package.json" -nt "node_modules" ]; then' >> /entrypoint.sh && \
    echo '  echo "Installing dependencies..."' >> /entrypoint.sh && \
    echo '  yarn install' >> /entrypoint.sh && \
    echo 'fi' >> /entrypoint.sh && \
    echo 'exec "$@"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh && \
    chown node:node /entrypoint.sh

USER node
ENTRYPOINT ["/entrypoint.sh"]
CMD ["yarn", "dev", "--host", "0.0.0.0"]
