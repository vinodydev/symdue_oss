# Flowgraph

Visual workflow runtime for AI agents — a durable, replay-safe substrate that turns nodes-and-edges diagrams into running, observable, long-lived workflows.

> **Status:** early public release. The polished marketing-grade README is on its way; this stub gives you enough to clone, run, and contribute.

## What's in this repo

- `server/` — FastAPI backend, Temporal workers, LangGraph executor, signal/wait/event runtime, storage backends.
- `client/` — React + TypeScript canvas UI.
- `setup/` — Docker Compose for the full local stack (Postgres, Redis, Temporal, MinIO, backend, worker, frontend).

## Quickstart

```bash
cp server/.env.example server/.env
cd setup
docker compose up
```

Then open `http://localhost:3000`.

For non-Docker dev setup, see [`setup/setup-mac.sh`](setup/setup-mac.sh) and [`setup/setup-db.sh`](setup/setup-db.sh).

## What's here vs. what's not

This repo ships the **runtime substrate**:

- Visual canvas with free-form, weighted edges
- Temporal-backed durable execution with replay-from-checkpoint
- Eight built-in node types (Input, Custom Python, Custom LLM, Condition, Workflow, Workflow Template, Iterator, Wait)
- Signal channels with fan-out + multi-mode wait nodes
- Queue-event-to-workflow-input
- Six storage backends (Postgres, Redis, MongoDB, Chroma, MinIO/S3, local file)
- LLM provider adapters (OpenAI, Anthropic, Gemini, Perplexity, Ollama)
- Per-node container isolation, refresh-safe canvas, JSON workflow export/import

Higher-level products built on top of this substrate (specialized agent stacks, expertise/reasoning systems, managed deployments) live elsewhere.

## License

[Apache License 2.0](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security disclosures go to [SECURITY.md](SECURITY.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
