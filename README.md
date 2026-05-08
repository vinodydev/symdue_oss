<p align="center">
  <img src=".github/banner.jpg" alt="Symdue" width="100%" />
</p>

<p align="center">
  <a href="https://youtu.be/aUr8gr9wKiA"><img src="https://img.shields.io/badge/▶_DEMO-red?style=for-the-badge" alt="Demo" /></a>
  <a href="docs/FAQ.md"><img src="https://img.shields.io/badge/DOCS-blue?style=for-the-badge" alt="Docs" /></a>
  <a href="docs/NODE_TYPE_API.md"><img src="https://img.shields.io/badge/PLUGIN_API-Apache_2.0-green?style=for-the-badge" alt="Plugin API" /></a>
  <a href="https://discord.gg/c3ysHGCyqs"><img src="https://img.shields.io/badge/DISCORD-Join-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/LICENSE-AGPL_v3_+_Apache_2.0_SDK-orange?style=for-the-badge" alt="License" /></a>
  <a href="https://github.com/vinodydev"><img src="https://img.shields.io/badge/BUILT_BY-vinody-black?style=for-the-badge" alt="Built by" /></a>
</p>

<p align="center"><b>Visual workflow runtime for AI agents — durable, replay-safe, container-isolated.</b></p>

> **Note**: This project's working name was "Flowgraph" during early development. Renamed to **Symdue** ahead of public launch. The demo video below was recorded under the old name and will be re-recorded shortly.

## Demo

<p align="center">
  <a href="https://youtu.be/aUr8gr9wKiA">
    <img src="https://img.youtube.com/vi/aUr8gr9wKiA/maxresdefault.jpg"
         alt="Symdue Deep Research Demo — 2 min" width="720" />
  </a>
  <br />
  <em>▶ Watch the 2-minute Deep Research demo</em>
</p>

The demo runs a Deep Research workflow that:

- **Fans out across multiple sources**: parallel `WEB_SEARCH`, `PAPER_SEARCH`, and `PDF_READ` nodes triggered from a single user prompt.
- **Iterates to refine**: configurable max-iteration loop — initial findings feed back into a second-pass query before the report is produced.
- **Produces a structured report**: HTML output with executive summary, perspectives, confidence map, and source list — generated from the run's actual retrieved content, not a freeform LLM completion.
- **Whitelists citations**: only sources that actually exist in the run's retrieval whitelist can be cited; fabricated references are dropped at the storage boundary, not patched in post.
- **Survives browser refresh**: workflows execute on a Temporal substrate. Closing the tab, refreshing, or restarting the browser does not stop or reset the run; the UI reconnects to the live state on reload.
- **Per-node observability**: click any node after a run to see its logs, inputs, and outputs — the same data the workflow saw at that step.

> **Status:** early public release. The polished marketing-grade README is on its way; this stub gives you enough to clone, run, and contribute.

## How Symdue fits next to existing tools

| Tool | What it's great at | Where Symdue is built differently |
|---|---|---|
| **n8n** | 600+ pre-built integrations, mature low-code editor, large community | Production durability where lost runs cost real money — workflows survive crashes mid-run, resume from arbitrary nodes, container isolation per code node |
| **LangGraph / LangChain** | Code-first agent orchestration with strong typed abstractions | Visual canvas alongside the code-first model, channel-signal fan-out, parallel updates with substrate-level reducers |
| **Temporal alone** | Industry-standard durable execution (Snap, Stripe, Coinbase) | Workflow editor + AI-shaped node abstractions on top of Temporal — Symdue *is* Temporal underneath |
| **Inngest** | Durable step functions with memoized resume, JS/TS-first | Visual canvas, Python + LLM-shaped node abstractions, declarative storage injection, container-isolated code nodes |
| **Trigger.dev** | TypeScript SDK with type-safety, CRIU checkpoint/resume, multi-env, atomic versioning | Visual canvas, Python + LLM primitives, declarative storage injection, container isolation, self-hosted-first |
| **Airflow / Prefect** | Battle-tested for scheduled batch ETL, mature schedulers | AI-agent-shaped workflows — LLM calls, HITL, iterative loops with feedback edges, replay-with-modified-inputs |

See [docs/COMPARISON.md](docs/COMPARISON.md) for per-tool deep-dives, citation-backed claims, and the full capability matrix.

### Symdue is for

- Teams running AI agent workflows in production where lost runs, hallucinated citations, or unrecoverable failures cost real money
- Engineering teams wanting a visual canvas + Temporal-backed durability + container isolation + declarative storage in one substrate
- Self-hosters who need full audit trails, replay-from-checkpoint, and no paywalled enterprise tier
- Builders shipping iterative agents (research, document analysis, lead pipelines) that need to survive crashes, restarts, and 6-hour LLM stalls
- Operators who want non-engineers to inspect and understand running workflows on a canvas

### Symdue is not for

- Simple cron-style ETL — use a dedicated scheduler
- Single-shot agent prototypes — overkill
- Teams happy with stateless workflows that re-run from scratch on any failure
- SaaS-to-SaaS automation without code or AI — purpose-built tools win that battle
- TypeScript-first teams who don't want a visual canvas — Inngest or Trigger.dev is a better shape

## What's in this repo

- `server/` — FastAPI backend, Temporal workers, LangGraph executor, signal/wait/event runtime, storage backends.
- `client/` — React + TypeScript canvas UI.
- `setup/` — Docker Compose for the full local stack (Postgres, Redis, Temporal, MinIO, backend, worker, frontend).

## Quickstart

```bash
# First time
./setup/symdue.sh init    # generates .env with random secrets, auto-detects Docker GID
./setup/symdue.sh start   # launches the stack (builds images on first run)

# Subsequent runs
./setup/symdue.sh start          # bring up if stopped
./setup/symdue.sh logs backend   # tail a service
./setup/symdue.sh rebuild        # full clean rebuild after pulling upstream changes
./setup/symdue.sh stop           # halt the stack
./setup/symdue.sh help           # full command list
```

Then open `http://localhost:3000`. Backend Swagger UI at `http://localhost:8000/docs`.

`symdue.sh` auto-detects your host's docker group GID, so `docker.sock` bind-mounts work without manual env-var prefixes.

For non-Docker dev setup, see [`setup/setup-mac.sh`](setup/setup-mac.sh) and [`setup/setup-db.sh`](setup/setup-db.sh). The older [`setup/run.sh`](setup/run.sh) still works but is deprecated in favor of `symdue.sh`.

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

Symdue uses a **dual-license** structure:

- **Runtime: AGPL v3** — protects against hyperscaler-managed-service forks while keeping the code genuinely open and self-hostable. Self-hosting, modifying for your needs, and integrating via API are unrestricted. The AGPL clause kicks in only if you modify the runtime AND make it network-accessible to third parties. Same model as Grafana and MongoDB.
- **Plugin SDK: Apache 2.0** — your custom NodeTypes are your IP. Build them against the Apache 2.0 SDK and license them however you want (proprietary, MIT, AGPL, etc.). Same legal pattern as MySQL connectors (LGPL) or PostgreSQL extensions (BSD).
- **Demo workflows: Apache 2.0** — copy, modify, integrate freely.

For specific use cases that need to escape AGPL on the runtime (embedding Symdue in closed-source SaaS, hyperscaler-class managed services, proprietary runtime modifications), see [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md).

Public commitments in [PRICING_PHILOSOPHY.md](PRICING_PHILOSOPHY.md): AGPL forever for the runtime, Apache forever for the SDK, no ads / no upsell prompts / no telemetry by default.

License files: [LICENSE](LICENSE) (overview) · [LICENSE-AGPL](LICENSE-AGPL) (full AGPL v3 text) · [LICENSE-APACHE](LICENSE-APACHE) (full Apache 2.0 text)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Runtime contributions require signing the [CLA](CLA.md) (one-click via CLA Assistant on first PR; standard for dual-licensed OSS projects). Apache 2.0 SDK / demo contributions accept Developer Certificate of Origin (DCO) sign-off only.

Security disclosures go to [SECURITY.md](SECURITY.md). This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).

---

Built solo in Hyderabad by [Vinod Y](https://github.com/vinodydev). Reach me at [vinody.dev@gmail.com](mailto:vinody.dev@gmail.com) — happy to talk through self-hosting, NodeType plugin design, or commercial licensing.
