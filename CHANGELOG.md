# Changelog

All notable changes to Symdue will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

(Track in-flight changes here between releases.)

## [0.1.0] — 2026-05-XX

Initial public release.

### Added

- Visual canvas with free-form weighted edges
- Temporal-backed durable workflow runtime with replay-from-checkpoint
- Eight built-in node types: Input, Custom Python, Custom LLM, Condition,
  Workflow, Workflow Template, Iterator, Wait
- Signal channels with fan-out + multi-mode wait nodes (signal, any, all,
  time, until)
- Six storage backends: Postgres, Redis, MongoDB, Chroma, MinIO/S3, local file
- LLM provider adapters: OpenAI, Anthropic, Google Gemini, Perplexity, Ollama
- Per-node container isolation for Custom Python nodes (Docker-out-of-Docker)
- Refresh-safe canvas — workflows survive page reloads mid-execution
- JSON workflow export/import
- Docker Compose stack with Postgres, Redis, MinIO, Temporal, Temporal UI

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

[Unreleased]: https://github.com/symdue/symdue/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/symdue/symdue/releases/tag/v0.1.0
