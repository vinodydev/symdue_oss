# Security Policy

## Supported versions

This project is in early public release. Security fixes will land on the `main` branch; tagged releases will follow once the project stabilizes.

## Trust model

Flowgraph is a workflow runtime substrate. By design it executes user-supplied Python in containers (Custom Python nodes), spawns containers via the host Docker daemon, and stores credentials for any LLM provider you connect. **The substrate is single-tenant** — it does not implement multi-user authentication or workspace isolation. Treat the running backend as a single trust domain.

Operate Flowgraph with these guardrails:

### 1. Do not expose the API to untrusted networks

The default Docker Compose binds backend port `8000` on `0.0.0.0`. The API has **no authentication** in the OSS substrate; anyone who can reach the port can read and write every workflow, run, and configuration.

For any non-localhost deployment, either:

- Bind the backend to `127.0.0.1` only (edit `setup/docker-compose.yml`):
  ```yaml
  backend:
    ports:
      - "127.0.0.1:8000:8000"
  ```
- Or front it with an authenticating reverse proxy (Caddy, nginx, Cloudflare Access, etc.).

Multi-user authentication is part of the closed managed/Cloud tier — not the OSS substrate.

### 2. Event scripts are disabled by default

The Event subsystem (`POST /api/events` with a Python `script` body, fired on a cron / interval / Redis-stream / webhook trigger) executes that script in the backend process. **It is gated off by default** via `EVENT_SCRIPTS_ENABLED=false`.

When the flag is `false` (default):
- `POST /api/events` and `PATCH /api/events/{id}` reject non-empty `script` payloads with `403`
- `POST /api/events/{id}/trigger` returns `503`
- The interval/cron scheduler does not run
- Redis-stream queue listeners do not start

To enable (e.g., for a single-tenant deployment behind an authenticating proxy on a host you control), set `EVENT_SCRIPTS_ENABLED=true`. **Do not enable on a network-reachable deployment without auth in front** — the script body has full Python and runs in the backend process.

For substrate scheduling without enabling the feature, see [docs/scheduling.md](docs/scheduling.md) — external cron, Wait+Signal channel, or webhook-receiver patterns.

### 3. The Docker socket is mounted into the backend by design

`setup/docker-compose.yml` bind-mounts `/var/run/docker.sock` into the backend and temporal-worker containers — this is required for spawning Custom Python node containers. The consequence: a code-execution compromise inside the backend container is equivalent to **root on the Docker host**.

This is a deliberate trust boundary. To reduce blast radius:

- Run Flowgraph on a host dedicated to it
- Enable Docker user-namespace remapping on the host (`/etc/docker/daemon.json` → `{ "userns-remap": "default" }`)
- For higher-paranoia deployments, run Custom Python nodes inside Sysbox or Kata-Containers (advanced; not yet documented in this repo)

### 4. Replace the placeholder secrets before exposure

`server/.env.example` ships with placeholders: `POSTGRES_PASSWORD=your_password`, `MINIO_ROOT_USER=minioadmin / MINIO_ROOT_PASSWORD=minioadmin`, `SECRET_KEY=your-secret-key-change-in-production`. The Docker Compose defaults reference these values directly via `${VAR:-placeholder}` syntax — meaning a `docker compose up` without populating `.env` produces a fully-functional Flowgraph using the documented placeholders.

Before any non-localhost deployment, generate real values:

```bash
# Suggested commands (Linux / macOS):
echo "POSTGRES_PASSWORD=$(openssl rand -base64 32)" >> .env
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
echo "MINIO_ROOT_USER=$(openssl rand -hex 8)" >> .env
echo "MINIO_ROOT_PASSWORD=$(openssl rand -base64 32)" >> .env
```

`minioadmin/minioadmin` in particular is the first credential pair every attacker tries against any MinIO instance they find.

## Reporting a vulnerability

**Please do not file public GitHub issues for security problems.**

Instead, email the maintainers privately at: **TODO — set this address before publishing**.

Include:

- A description of the issue and its impact
- Reproduction steps (or proof-of-concept)
- The commit hash or version you tested against
- Whether you've shared this with anyone else

We'll acknowledge receipt within 5 business days and aim to provide a remediation timeline within 14 days. Coordinated disclosure is appreciated — we'll work with you on a public advisory once a fix is ready.
