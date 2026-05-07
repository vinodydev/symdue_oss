# Changelog

All notable changes to Symdue will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(Track in-flight changes here between releases.)

## [0.1.0-agpl] — 2026-05-07

Initial public release.

### Added

- Visual canvas with free-form weighted edges
- Temporal-backed durable workflow runtime with replay-from-checkpoint
- Built-in node types: Input, Custom Python, Custom LLM, Condition (Python),
  Memory, Wait, HTML Viewer
- Iterator mode (config flag on Custom Python / Custom LLM nodes) for
  "for each item" parallelism
- Workflow-as-Node (sub-workflow embedding via the `workflow_node`
  reference type)
- Workflow templates (importable workflow JSON snapshots)
- Signal channels with fan-out + multi-mode wait nodes (signal, any, all,
  time, until)
- Six storage backends: Postgres (with optional pgvector), Redis, MongoDB,
  Chroma, MinIO/S3, local file
- LLM provider adapters: OpenAI, Anthropic, Google Gemini
- Per-node container isolation for Custom Python nodes (Docker-out-of-Docker)
- Auto-embedding for vector storages (sentence-transformers
  `BAAI/bge-small-en-v1.5` baked into the backend image)
- Refresh-safe canvas — workflows survive page reloads mid-execution
- JSON workflow export/import
- Docker Compose stack with Postgres, Redis, MinIO, Temporal, Temporal UI

### License

This is Symdue's first public release under a **dual license**:

- **Runtime: AGPL v3** — protects against hyperscaler-managed-service forks
  while keeping the code genuinely open and self-hostable.
- **Plugin SDK + workflow JSON spec: Apache 2.0** — custom NodeTypes built
  against the SDK are separate works owned by their authors. Same legal
  pattern as PostgreSQL extensions, MySQL connectors, Linux kernel modules.
- **Demo workflows: Apache 2.0** — copy, modify, integrate freely.

Same dual-license model as Grafana and MongoDB. See [LICENSE](LICENSE),
[PRICING_PHILOSOPHY.md](PRICING_PHILOSOPHY.md),
[COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md), and
[docs/NODE_TYPE_API.md](docs/NODE_TYPE_API.md) for the public commitments
and the versioned plugin contract.

Project rebranded from "Flowgraph" (working name during early development)
to **Symdue** ahead of public launch — same product, name change only.
Demo video voiceover still says "Flowgraph" and will be re-recorded shortly.

Runtime contributors sign a [CLA](CLA.md) (HarmonyCLA template); plugin
SDK / demo contributions accept DCO sign-off.

### Security

- Event scripts (`POST /api/events` with a Python `script` body, fired on
  cron / interval / queue triggers) are **disabled by default** via
  `EVENT_SCRIPTS_ENABLED=false`. To enable, see [SECURITY.md](SECURITY.md).
  Operators must front the substrate with an authenticating proxy before
  enabling. Closes the unauthenticated RCE attack path at the HTTP boundary.
- All host port bindings (Postgres, Redis, MinIO, Temporal, backend, frontend)
  default to `127.0.0.1` only — explicit operator action required to expose
  on a network. See [SECURITY.md](SECURITY.md) "Trust model".

### Known limitations

- **No multi-user authentication.** The OSS substrate is single-tenant; deploy
  behind an authenticating reverse proxy or use the managed BYOC tier when
  available.
- **No built-in scheduling primitive.** The Event-script feature is gated off;
  for scheduled work, use external cron + `curl POST /api/runs`, or a Wait
  node + signal channel pattern. See [docs/scheduling.md](docs/scheduling.md).
- **Pre-existing bug:** using a Python node inside an Iterator node currently
  raises `NameError: name 'workflow_id' is not defined`. Workaround: use a
  Custom Python node outside the Iterator until v0.1.1.
- **Pre-existing test drift:** several frontend tests assume an older `Node`
  interface that's missing the `name` field; ~14 vitest failures. Tracked
  for v0.1.1.

[Unreleased]: https://github.com/vinodydev/symdue_oss/compare/v0.1.0-agpl...HEAD
[0.1.0-agpl]: https://github.com/vinodydev/symdue_oss/releases/tag/v0.1.0-agpl
