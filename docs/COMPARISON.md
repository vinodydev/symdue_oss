<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Symdue contributors -->

# Symdue vs alternatives

How Symdue fits next to other workflow runtimes and AI-agent orchestrators. Each section leads with what the competitor is genuinely good at, then states where Symdue is built differently. No combative framing.

## Quick-scan: how Symdue fits next to existing tools

| Tool | What it's great at | Where Symdue is built differently |
|---|---|---|
| **n8n** | 600+ pre-built integrations, mature low-code editor, large community, fastest path from idea to running workflow | Production durability where lost runs cost real money — workflows survive crashes mid-run, resume from arbitrary nodes, HITL pauses survive deploys, container isolation per code node |
| **LangGraph / LangChain** | Code-first agent orchestration, deep ecosystem, strong abstractions for graph-based agents | Visual canvas alongside the code-first model, channel-signal fan-out (vs per-thread interrupts), parallel updates with substrate-level reducers |
| **Temporal alone** | Industry-standard durable execution, used by Snap, Stripe, Coinbase | Workflow editor + AI-shaped node abstractions on top of Temporal — Symdue *is* Temporal underneath plus visual + LLM nodes |
| **Inngest** | Durable step functions with memoized resume, JS/TS first, built-in concurrency/throttling/idempotency | Visual canvas, Python + LLM-shaped node abstractions, declarative storage injection, container-isolated code nodes |
| **Trigger.dev** | TypeScript-first SDK with end-to-end Zod type-safety, CRIU-based checkpoint/resume, multi-env (DEV/PREVIEW/STAGING/PROD), atomic versioning, OpenTelemetry observability, managed elastic cloud | Visual canvas, Python + LLM-shaped primitives, declarative storage injection across 6 backends, container isolation per node, self-hosted-first |
| **Airflow / Prefect** | Battle-tested for scheduled batch ETL, mature schedulers, deep observability | AI-agent-shaped workflows — LLM calls, HITL, iterative loops with feedback edges, replay-with-modified-inputs |

---

## Per-tool deep-dives

### vs n8n

**What n8n excels at:** 600+ pre-built SaaS integrations. Mature low-code editor used by thousands of agencies. Fastest tool to ship a webhook-triggered workflow in 10 minutes. Large active community. Best choice when integration breadth is the primary requirement and workflows are short, stateless, and idempotent on retry.

**Where Symdue is built differently for the same buyer:**

- **The 3am stuck-running run.** n8n's BullMQ + Postgres-rows architecture means a worker OOM at node 47 of a 50-node workflow leaves the `execution` row stuck in `running` indefinitely with no UI recovery — documented across community threads [#54461](https://community.n8n.io/t/execution-status-is-running-almost-24-hrs-and-cannot-be-stopped/54461), [#239431](https://community.n8n.io/t/execution-queue-stuck/239431), [#275978](https://community.n8n.io/t/worker-crash-mid-execution-in-queue/275978), GH [#17395](https://github.com/n8n-io/n8n/issues/17395). Symdue's Temporal-backed activity history persists every step; on worker death the workflow resumes on a new worker with no state-corruption window.

- **Resume from node 4 without re-paying nodes 1-3.** Six-year-old open feature request: [n8n community thread #800 since 2019](https://community.n8n.io/t/restart-workflow-from-specific-node/800); related bugs [#17670](https://github.com/n8n-io/n8n/issues/17670), [#21778](https://github.com/n8n-io/n8n/issues/21778) re-run the upstream chain even with pinned data. Symdue's `POST /resume-from` builds `initial_state` from the source run's snapshot and the skip-if-done predicate skips every node already populated — net effect: only missing/errored nodes re-execute. 4-step LLM workflow with a typo in step 4 → fix step 4, hit Resume → only step 4 re-runs.

- **6-hour HITL approval that survives a rolling deploy.** n8n's `Respond to callback` is [documented broken with Wait "On webhook call" in current versions (issue #13633)](https://github.com/n8n-io/n8n/issues/13633). Symdue's Wait nodes persist a row in `workflow_waits` (`run_id`, `node_id`, `channel`, `mode`, `signals_needed`, `timeout_at`); Temporal `wait_condition(timeout)` blocks until satisfied, restoring across worker reboots. Five wait modes — `signal`, `any`, `all`, `time`, `until`.

- **Per-node container isolation with declared pip requirements.** n8n's Code node runs in the shared Node.js process; the Function node is `vm2`-sandboxed JS only. Symdue runs each Python node in a fresh `python:3.11-slim` Docker container with `mem_limit="512m"`, 50% CPU quota, and per-run pip install — auto-injecting backend deps when storages are declared (postgres → psycopg2, redis → redis, mongodb → pymongo, chroma → chromadb, minio → boto3).

- **Cross-environment storage credentials without code changes.** Each n8n integration node implements its own credentials; custom nodes need bespoke per-env handling. Symdue's NodeType declares `"storages": ["minio"]`; the runtime resolves `default_minio` from the workspace's `StorageConfig` and injects a pre-instantiated `StorageClient` — same node code in dev MinIO, staging internal-S3, prod AWS S3. Six backends (Postgres, Redis, Mongo, Chroma, MinIO/S3, local file).

- **Refresh-safe canvas mid-run.** n8n's editor refresh mid-run loses live highlight state; results require reopening from the Executions list. Symdue persists per-node snapshots after every step; on app load the canvas seeds itself from `node_outputs` across three trigger-points (completion, WebSocket reconnect, tab `visibilitychange`).

---

### vs LangGraph / LangChain

**What LangGraph excels at:** Code-first agent orchestration with strong typed abstractions. Per-thread interrupts for human-in-the-loop. Deep LangChain ecosystem of LLM/tool integrations. Best choice when the team is Python-first, prefers all logic in code, and doesn't need a visual canvas.

**Where Symdue is built differently:**

- **Visual canvas alongside the code-first model.** LangGraph requires Python expertise to inspect runs — graph state is a programmer's view. Symdue exposes graph state on a canvas non-engineers can read: running, stuck, replayed, with edge highlights along successful paths and per-node properties panels. Symdue *uses* LangGraph as the underlying execution engine — the canvas is layered on top, not a replacement for LangGraph's primitives.

- **Channel-signal fan-out vs per-thread interrupts.** LangGraph's `interrupt()` is per-thread — no first-class "send signal to channel `approve`, all subscribed waits resolve" primitive. Symdue's signal channels fan out to every wait node on a channel (capped at `signal_channel_max_fanout`, default 100) with five subscriber modes.

- **Parallel fan-out without `InvalidUpdateError`.** Naive LangGraph users hit `InvalidUpdateError` when two nodes return the same key — the fix requires custom reducers; most teams burn hours on Stack Overflow. Symdue's `GraphState` is a `TypedDict` whose mutable fields use `Annotated` reducers (`merge_dicts`, `replace_list`, `take_max_step`) at the substrate level. Reducer choice isn't a per-workflow concern.

- **Same Temporal-grade durability under the hood.** LangGraph's `MemorySaver` / `PostgresSaver` provide checkpointing; Symdue inherits Temporal's full event-history durability + per-node Postgres snapshots. Activity-result data is kept under the 4 MB Temporal cap; heavy data (full outputs, logs, embeddings) is offloaded to `node_execution_history` (gzip BYTEA).

---

### vs Temporal alone

**What Temporal excels at:** Industry-standard durable execution primitive. Used by Snap, Stripe, Coinbase. Production-proven for workflows lasting days to months. Strong choice when the team is comfortable writing workflow code in Go, Java, Python, or TypeScript and doesn't need a visual editor or AI-shaped abstractions.

**Where Symdue fits:**

Symdue is built **on top of** Temporal — `GraphExecutorWorkflow.run(workflow_id, graph_json, inputs, run_id, initial_state?)` is the Temporal workflow. The value Symdue adds:

- **AI-shaped node abstractions.** Built-in node types ship in OSS: Input, Custom Python, Custom LLM, Condition, Memory, Wait, HTML Viewer. Plus a v1.0 NodeType plugin contract for custom types. Not roll-your-own activity definitions.

- **Visual canvas for non-engineers.** Operators run, pause, inspect workflows without reading workflow code. Refresh-safe.

- **Pre-built LLM and storage layers.** OpenAI, Anthropic, Gemini via per-workspace `LLMConfig`. Six storage backends (Postgres, Redis, Mongo, Chroma, MinIO/S3, local file) auto-injected per declared aliases.

- **Multimodal placeholder rewriting.** `{node_name}` placeholders in LLM prompts auto-detect upstream output type; image URLs become provider-specific image content blocks (OpenAI vision, Anthropic image, Gemini inline data). Switching providers is changing the model name.

**Source:** [temporal docs](https://docs.temporal.io)

---

### vs Inngest

**What Inngest excels at:** Durable step functions with automatic memoized resume — each step runs once, result persisted, retries skip completed steps. JS/TS-first SDK. Built-in concurrency, throttling, debouncing, rate limiting, idempotency — all available local / self-hosted / cloud. Strong choice for backend teams writing TypeScript who want durable workflows without a separate workflow-engine deployment.

**Where Symdue is built differently:**

- **Visual canvas + Python + LLM-shaped abstractions.** Inngest is code-first JS/TS — you write step functions; the platform memoizes them. Symdue is canvas-first with built-in node types and a NodeType plugin contract. Different audience: code-first JS/TS teams pick Inngest; teams that want non-engineers to read and operate the workflow pick Symdue.

- **Container isolation per code node.** Inngest steps run in the host process (or your serverless function); Symdue's Python nodes run in fresh `python:3.11-slim` Docker containers with declared pip requirements, 512MB / 50% CPU limits, dynamic dependency injection.

- **Declarative storage injection.** Inngest doesn't ship a storage abstraction; you `import` your DB/blob clients directly in step code. Symdue's `storages` dict is auto-resolved per workspace `StorageConfig`; same code targets local file in dev → MinIO in staging → AWS S3 in prod.

- **`waitForEvent` and `waitForSignal` in both — different abstraction surface.** Inngest's `step.waitForEvent` and `step.waitForSignal` are Promise-returning JS calls inside step code. Symdue's Wait nodes are first-class graph primitives with five modes (`signal`, `any`, `all`, `time`, `until`) and named-channel fan-out persisted in `workflow_waits`. Same durability guarantees; different authoring surface.

- **Iterators with per-item progress and dot-notation array extraction.** Inngest provides loop primitives in code; Symdue's iterator config is declarative on any node that opts in (`supports_iterator: true`), with `array_key` dot-notation extraction, `error_strategy: continue|stop`, and per-item Redis pubsub progress that renders a canvas progress bar.

**Sources:** [Inngest docs](https://www.inngest.com/docs), [Inngest GitHub](https://github.com/inngest/inngest)

---

### vs Trigger.dev

**What Trigger.dev excels at:** TypeScript-first SDK with end-to-end type safety via Zod schemas auto-converted to type-safe AI SDK tools. CRIU-based checkpoint/resume so tasks pause with **zero idle compute cost**. First-class multi-environment promotion (DEV / PREVIEW / STAGING / PROD). Atomic versioning. OpenTelemetry-powered live trace observability. React hooks for waitpoint resumption. Auto-scaling elastic infrastructure on managed cloud. **Cron schedules up to 1 year, no timeouts at all.** Strong choice for TypeScript backend teams shipping AI agents on managed infrastructure with mature DevEx around environments and observability.

**Where Symdue is built differently:**

- **Visual canvas + Python + LLM-shaped node abstractions.** Trigger.dev is code-only TypeScript — you write tasks; the platform handles durability and scaling. Symdue is canvas-first with built-in node types and a v1.0 NodeType plugin contract. Different audience: TS-native teams that prefer code primitives pick Trigger.dev; teams that want non-engineers to read and operate workflows on a canvas pick Symdue.

- **Per-node Docker isolation with declared pip + dynamic dependency injection.** Trigger.dev's tasks run on its managed runtime with configurable machines (vCPUs/RAM); the runtime owns the execution model. Symdue runs each Python node in a fresh `python:3.11-slim` Docker container with `mem_limit="512m"`, 50% CPU quota, and per-run pip install — auto-injecting backend dependencies when storages are declared (postgres → psycopg2, redis → redis, mongodb → pymongo, chroma → chromadb, minio → boto3). Two different bets on isolation: managed-runtime sandboxing (Trigger.dev) vs explicit-container-per-node (Symdue).

- **Declarative storage injection across 6 backends.** Trigger.dev doesn't ship a workspace-scoped storage abstraction; you `import` DB/blob clients directly in task code. Symdue's `storages` dict is auto-resolved per workspace `StorageConfig`; same code targets local file in dev → MinIO in staging → AWS S3 in prod, with credentials never visible to user code.

- **AI-shaped primitives ship in OSS.** Trigger.dev's AI agent story is "your task gets type-safe tools via Zod" — the actual LLM call orchestration is what you write inside tasks. Symdue's `custom-llm` node ships with provider auto-routing across OpenAI / Anthropic / Gemini, per-call cost tracking (input/output tokens + USD), iterator support, and multimodal placeholder rewriting (`{node_name}` → provider-specific image content blocks).

- **Self-hosted-first vs managed-cloud-first.** Trigger.dev's primary deployment is its managed cloud with auto-scaling and elastic infra; OSS exists but the commercial gravity is around the cloud product. Symdue is AGPL v3 self-hosted from day one — same features in OSS as in BYOC managed deployment, no paywalled enterprise tier.

- **Iterators with declarative array extraction and per-item canvas progress.** Trigger.dev provides loop primitives in code. Symdue's iterator config is declarative on any node that opts in (`supports_iterator: true`), with `array_key` dot-notation extraction (`data.results`), `error_strategy: continue|stop`, and per-item Redis pubsub progress that renders a canvas progress bar.

- **Where Trigger.dev wins outright (worth acknowledging):** multi-env promotion as a first-class primitive, atomic versioning, OpenTelemetry observability, React hooks for waitpoint resumption, and auto-scaling elastic cloud. Symdue's workspace-scoped isolation isn't multi-env; observability is WebSocket events not OTel; auto-scaling is operator-managed in self-hosted.

**Sources:** [Trigger.dev v3 announcement](https://trigger.dev/blog/v3-announcement), [Trigger.dev product / AI agents](https://trigger.dev/product/ai-agents), [Trigger.dev how it works](https://trigger.dev/docs/how-it-works), [Trigger.dev YC profile](https://www.ycombinator.com/companies/trigger-dev)

---

### vs Airflow / Prefect

**What Airflow and Prefect excel at:** Battle-tested for scheduled batch ETL pipelines. Mature schedulers (cron, time-based DAGs) with deep observability. Strong choice when workflows are scheduled, deterministic, ETL-shaped (extract → transform → load), and the team is comfortable with DAG-style declarative code.

**Where Symdue is built differently:**

- **AI-agent-shaped, not batch-shaped.** Airflow's DAG model assumes deterministic tasks with declared inputs. AI agent workflows are non-deterministic, often involve LLM calls returning structured-but-variable output, and benefit from iterative refinement loops with feedback edges — supported in Symdue via back-edge cycles with `MAX_GRAPH_STEPS` guard (default 1000).

- **Human-in-the-loop is first-class.** Airflow's "wait for external signal" patterns require sensor operators that poll. Symdue's Wait nodes are durable signal-channel subscribers; a contract-approval wait survives 6 hours of approver inactivity plus a worker rolling deploy.

- **Replay-with-modified-inputs eval.** Airflow can re-run a DAG from a clear date but doesn't expose `from_run_id` + `start_from_node_id` + modified-state replay as a primitive. Symdue's resume API supports prompt-eval-against-historical-inputs — change a prompt, re-run against the same 100 historical inputs without re-paying upstream LLM calls.

- **LLM-shaped primitives ship in OSS.** Airflow doesn't ship LLM nodes; you'd write Python operators that call provider SDKs. Symdue's `custom-llm` node ships with provider auto-routing (OpenAI, Anthropic, Gemini), per-call cost tracking, multimodal placeholder rewriting, and iterator support out of the box.

---

## Adjacent ecosystem (briefer)

These are tools that sometimes come up in comparison conversations.

### vs Zapier / Make

Zapier and Make excel at SaaS-to-SaaS integration breadth and dead-simple UX for non-developers. Symdue's space is self-hosted, code-customizable workflows with full audit trails, container isolation, and no per-task pricing on volume runs. Different audience: Zapier/Make for SaaS-to-SaaS without code; Symdue for AI-agent and code-bearing workflows that must run in production with crash-recovery and replay.

### vs Dify / Flowise / Langflow

These excel at quick AI workflow prototyping with friendly visual editors — strong demo flow. Symdue is built for graduation from prototype to production: in-memory state replaced with Temporal-persistent history; SSE-attached refresh replaced with snapshot-seeded canvas; manual merge logic replaced with substrate-level reducers; text-only prompt placeholders replaced with provider-aware multimodal blocks. Citation whitelisting (`fabricated_hashes_dropped` per iteration) prevents hallucinated sources at the storage boundary — not a feature these prototyping tools provide.

### vs Windmill

Windmill excels at code-first workflow runtime with strong TypeScript / Python / Go scripting, versioned scripts as the primitive, OSS, and mature CI/CD. Symdue is built differently: snapshot-skip-if-done resume vs per-step URL resume; channel-signal pub/sub vs URL-per-step approvals; Redis-Streams XREAD streaming triggers vs schedule/webhook-only; per-workspace storage attachments vs per-script Resources.

---

## Capability matrix

✅ = ships in Symdue OSS today, ◐ = partial/conditional, ❌ = not present.

| Capability | n8n | LangGraph | Temporal | Inngest | Trigger.dev | Airflow / Prefect | Symdue |
|---|---|---|---|---|---|---|---|
| Worker crash mid-run, no stuck rows | ❌ ([#17395](https://github.com/n8n-io/n8n/issues/17395)) | ✅ | ✅ | ✅ | ✅ (CRIU checkpoint) | ✅ | ✅ |
| Resume from arbitrary node, skip-if-done | ❌ ([6-yr request](https://community.n8n.io/t/restart-workflow-from-specific-node/800)) | ◐ (per-thread) | ✅ (activity replay) | ◐ (memoized steps) | ✅ (CRIU resume) | ❌ | ✅ |
| Mid-graph durable wait + signal fan-out | ◐ ([#13633](https://github.com/n8n-io/n8n/issues/13633)) | ◐ (interrupt, per-thread) | ✅ (signal) | ✅ (waitForEvent / waitForSignal) | ✅ (waitpoints + React hooks) | ❌ | ✅ |
| Container isolation per code node | ❌ | ❌ | ❌ | ❌ | ◐ (managed-runtime sandboxing) | ◐ (KubernetesPodOperator) | ✅ |
| Declarative storage injection per workspace | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| LLM nodes with provider auto-routing | ❌ (DIY in Code) | ◐ (LangChain integrations) | ❌ | ❌ | ◐ (Zod-typed AI SDK tools) | ❌ | ✅ |
| Provider-aware multimodal placeholders | ❌ | ◐ (manual) | ❌ | ❌ | ❌ | ❌ | ✅ |
| Iterators with per-item progress | ◐ (Split In Batches) | ❌ | ❌ | ◐ (loops in code) | ◐ (loops in code) | ❌ | ✅ |
| Back-edge loops with cycle guard | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| Refresh-safe canvas mid-run | ❌ | n/a (no canvas) | n/a | n/a | n/a | ❌ | ✅ |
| JSON workflow export/import (round-trip) | ✅ | n/a | n/a | n/a | n/a (code in repo) | ◐ (DAG code in repo) | ✅ |
| Visual canvas for non-engineers | ✅ | ❌ | ❌ | ❌ | ❌ | ◐ (DAG view, read-only) | ✅ |
| Sub-workflow with parent ↔ child navigation | ◐ (Execute Workflow) | ❌ | ◐ (child workflows) | ◐ (invoke) | ◐ (triggerByTask) | ❌ | ✅ |
| Cost tracking per LLM call | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Custom node plugin contract (registered) | ✅ | ❌ | n/a | ❌ | ❌ | ◐ (custom operators) | ✅ |
| Multi-environment promotion (DEV/STAGING/PROD) | ❌ | n/a | n/a | ◐ (envs in cloud) | ✅ (4-env first-class) | ◐ (operator-managed) | ❌ (workspace-scoped only) |
| Atomic versioning of workflows | ◐ | n/a | n/a | ◐ | ✅ | ◐ | ❌ |
| OpenTelemetry observability | ❌ | ❌ | ✅ | ◐ | ✅ | ✅ | ❌ (WebSocket events only) |

Empty cell `n/a` = not applicable to that tool's category.

---

## Symdue is for

- Teams running AI agent workflows in production where lost runs, hallucinated citations, or unrecoverable failures cost real money
- Engineering teams wanting a visual canvas + Temporal-backed durability + container isolation + declarative storage in one substrate
- Self-hosters who need full audit trails, replay-from-checkpoint, and no paywalled enterprise tier
- Builders shipping iterative agents (research, document analysis, lead pipelines) that need to survive crashes, restarts, and 6-hour LLM stalls
- Operators who want non-engineers to inspect and understand running workflows on a canvas

## Symdue is not for

- Simple cron-style ETL — use a dedicated scheduler
- Single-shot agent prototypes — overkill
- Teams happy with stateless workflows that re-run from scratch on any failure
- SaaS-to-SaaS automation without code or AI — purpose-built tools win that battle
- TypeScript-first teams who don't want a visual canvas — Inngest or Trigger.dev is a better shape
