# Frequently Asked Questions

This FAQ explains what Symdue is, why it exists, the production failure patterns it was built to handle, and the tradeoffs we made along the way. If you're evaluating Symdue for production AI workflows, start with **§1: What Symdue is** and **§3: The ten production scenarios** — those are the questions buyers actually ask.

---

## §1: What Symdue is

### What is Symdue in one sentence?

A visual editor for LLM and Python workflows on an infinite canvas, paired with a Temporal-backed durable runtime that streams every node transition back to the canvas in real time — and an autonomous agent runtime that uses the same primitives.

### Is this a no-code tool?

No. Symdue assumes engineers are in the loop. The canvas is a shared surface — engineers author Python and LLM nodes, while PMs, ops, and analysts can read the graph, watch a run, and pause it at 3am without learning Python. We don't replace code; we make code observable, durable, and re-runnable on a graph.

### Is this for agents, RAG pipelines, or ETL?

All three on the same substrate.

- **Agents** = LLM nodes + iterators + wait-for-signal + condition routing
- **RAG** = LLM nodes + storage-attached vector backends (Chroma, MongoDB, Postgres-pgvector)
- **ETL** = Python nodes + scheduled events + queue events

The same canvas, same runtime, same replay UI. There is no separate "agents product" vs "workflows product."

### Self-hosted, cloud, or both?

Self-hosted-first. `docker compose up` runs the full stack — Postgres, Redis, Temporal, MinIO, backend, worker, frontend — locally. We also offer managed BYOC (we run Symdue on your cloud account) for teams that want production deployment handled. There is no shared multi-tenant SaaS, by design — see §4.

### What's the license?

**Dual-license**: AGPL v3 for the runtime + Apache 2.0 for the plugin SDK and spec.

- **Runtime** (`server/`, `client/`, `setup/`): GNU AGPL v3.0 or later
- **Plugin SDK + spec** (`server/schemas/`, demos): Apache 2.0
- **Demo content** (`demos/`): Apache 2.0

This means: self-hosting and internal use are unrestricted; building custom NodeTypes against the Apache SDK lets you license your NodeType code however you want; modifications to the AGPL'd runtime that you make network-accessible to third parties trigger AGPL obligations.

Same model as Grafana (AGPL Grafana + permissive plugin API) and MongoDB (AGPL → SSPL → Atlas Cloud is closed).

For specific use cases that need to escape AGPL on the runtime (embedded SaaS, hyperscaler-class managed service, proprietary modifications), see [COMMERCIAL_LICENSE.md](../COMMERCIAL_LICENSE.md).

Public commitments in [PRICING_PHILOSOPHY.md](../PRICING_PHILOSOPHY.md).

### Who is this for?

Small AI product teams at 50–500-person companies who have prototyped in a notebook or a visual builder and now need to put a workflow into production with replay, observability, and human-in-the-loop pauses. They've outgrown the prototyping tool and don't want to commit to a code-first runtime that has no canvas. They want both.

### Is Symdue a product or a framework?

A product with a framework underneath. The canvas, run history, replay UI, signals/events page, and storage-attached node types are product. The Python-nodes-in-Docker model, Temporal + LangGraph executor, snapshot-per-step + skip-if-done logic, and RuntimeAPI are the framework. You can use either layer.

---

## §2: Why this exists — what current workflow stacks miss

Most workflow automation tools today fall into one of three camps, each with a structural ceiling:

1. **Polished visual builders** with hundreds of integrations but a runtime that loses execution state on worker crashes, can't resume from arbitrary nodes, and treats workflow runs as one-shot jobs rather than durable processes.
2. **Code-first agent libraries** with strong runtime semantics but no visual surface — debugging a multi-step agent at 3am means reading logs and reconstructing state in your head.
3. **Generic workflow engines** with durability but no LLM-native primitives — every prompt template is a string-format call you write yourself, and provider differences leak into your application code.

Symdue occupies the gap: **visual + durable + LLM-native + event-driven** in one substrate. The next ten sections cover the specific production failure patterns that drove this design.

---

## §3: The ten production scenarios

Each scenario describes a real production failure pattern, why typical stacks struggle with it (without naming products), and how Symdue handles it.

### Scenario 1: The 3am stuck-running run

**Setup:** A nightly RAG-refresh workflow runs 50 LLM nodes against your knowledge base. At node 47, the worker OOMs and dies.

**Common failure pattern:** The execution row in the database is stuck in `running` indefinitely. The UI offers no way to stop it. Recovery is "SSH into the database and `UPDATE execution SET status = 'error'`." Worker death becomes a state-corruption event because run progress lives only in the worker's memory and a status column.

**How Symdue handles it:** Temporal persists the workflow's history events. On worker restart, the workflow resumes from the last completed event. Every node writes a partial snapshot to Postgres after it completes. The "stuck running" failure mode doesn't exist because state and progress are externalized by construction.

### Scenario 2: Resume from a typo without re-paying for upstream LLM calls

**Setup:** Your workflow has 4 LLM nodes. The 4th has a typo in the prompt. You fix it. You don't want to re-pay $0.50 + $1.20 + $0.80 = $2.50 for the upstream calls.

**Common failure pattern:** Native execution data is read-only after the run; you cannot resume a partially-completed graph from an arbitrary node with prior outputs preserved. The workaround is "pin past output as new input" — a manual copy-paste loop, not a graph-aware resume. This pattern is a multi-year community feature request in many tools.

**How Symdue handles it:** A "Resume from here" button on every failed, cancelled, or partial run. The skip-if-done predicate checks `state["node_outputs"][node_id]` and skips any node that already has a non-error entry. You re-pay for one LLM call, not four.

### Scenario 3: A 6-hour human-approval pause that survives a worker reboot

**Setup:** Approval workflow — agent generates a contract → waits for a human's "approve" or "reject" signal → if approved, sends to counterparty. Approver is on a flight, the wait is 6 hours, and your worker fleet does a rolling deploy halfway through.

**Common failure pattern:** Wait nodes bind a single-execution `resumeUrl`. There's no named-channel signal abstraction; multi-listener fan-out, "all-of" / "any-of" semantics are absent. And the most common HITL pattern (pause, callback, respond synchronously) is documented as broken in current versions of mainstream stacks.

**How Symdue handles it:** Wait nodes persist a row in `workflow_waits` (`run_id`, `node_id`, `channel`, `mode`, `signals_needed`, `timeout_at`) and emit `__suspended__: true` into graph state. The Temporal workflow enters `wait_condition` until the signal arrives. Worker reboots are irrelevant — Temporal restores the workflow from history. Five wait modes (`signal`, `any`, `all`, `time`, `until`) cover the real shapes of human-approval flows.

### Scenario 4: 10,000 events/hour each kicking off a workflow with the event as input

**Setup:** A Kafka topic emits 10k user-event messages per hour. Each should fire a workflow with the event payload as that workflow's `inputs`. You want this productized, not glue code you maintain.

**Common failure pattern:** Trigger nodes can fire on webhook, but feeding the message body as workflow `inputs` per event with audit + dead-letter handling means you write the glue. Workflow-as-API is well-supported; data-stream-to-workflow-with-inputs is typically not. Per-operation pricing in some hosted tools makes 10k/hour fan-out economically painful even when technically possible.

**How Symdue handles it:** Queue events block on Redis Streams `XREAD` per `queue_name`. When a message arrives, the event script fires with `input_data` set to the message body. The script calls `runtime.run_workflow(name, inputs=data)` to spawn a workflow run with the arriving payload as its inputs. Every API call is recorded in `EventInvocation.runtime_calls` for audit. End-to-end data-triggerable, no glue.

### Scenario 5: The closed-tab user

**Setup:** A non-engineer kicks off a 20-minute run, gets distracted, closes the browser tab, comes back 15 minutes later. What do they see?

**Common failure pattern:** Refreshing the editor mid-run loses live highlight state. You reopen the execution from the executions list to see results — a different surface, not the canvas you were watching. Build modes that use SSE attach to the in-flight job, and reconnection isn't well-documented when the tab is closed.

**How Symdue handles it:** After every node completes, a partial snapshot is written to Postgres. On app load, an effect reads the active run's snapshot and seeds node statuses (`success` / `error` / `waiting` / `blocked`) so the canvas is correct without waiting for new WebSocket frames. Three trigger points refetch on completion, on WebSocket reconnect, and on tab `visibilitychange`.

### Scenario 6: Eval against a frozen set of historical inputs

**Setup:** You changed a prompt. You want to test the change against the same 100 historical user inputs without re-running the upstream tools or paying for upstream LLM calls.

**Common failure pattern:** "Debug in editor" pins past output as new input — manual, one execution at a time. No batch eval primitive. Eval is typically a separate product bolted on top of the workflow tool.

**How Symdue handles it:** Replay-from-checkpoint generalizes to replay-with-modified-inputs. The resume API accepts `from_run_id` + optional `start_from_node_id`, reconstructs `initial_state` from the source run's snapshot, modifies what you want, re-runs. Skip-if-done preserves all upstream nodes' outputs verbatim. Run history is a first-class eval substrate, not a separate product.

### Scenario 7: Same custom node, dev MinIO and prod S3, zero code changes

**Setup:** You write a custom screenshot-uploader Python node. You want it to work in dev against MinIO, in staging against an internal S3, and in prod against AWS S3 — without changing the node's code.

**Common failure pattern:** Each integration node implements its own credentials. Custom nodes need bespoke credential handling per environment. Per-script resources are referenced by ID; promotion across environments is mechanical but manual.

**How Symdue handles it:** Storage-attached nodes. The NodeType declares `"storages": ["minio"]`. The runtime auto-resolves `default_minio` from the `StorageConfig` table per workspace, copies the StorageClient + backend module into the container, and injects a `storages` dict via `initialize(config, storages)`. The node's code is `storages["minio"].upload(key, bytes)` — same code in dev, staging, prod. Six backends supported (MinIO/S3, Postgres, Mongo, Redis, Chroma, local file).

### Scenario 8: Multi-agent system with parent ↔ child run navigation

**Setup:** You build a multi-agent system where the parent orchestrator calls 5 specialist agents, each of which is its own workflow. When debugging, you need to drill from a parent run into a specialist's run and back.

**Common failure pattern:** Sub-workflows exist via "execute workflow" nodes. UI navigation is breadcrumb-style or implicit, not a "open child run with child run pre-selected" surface. Replay-from-step is per-flow, not parent-child threaded.

**How Symdue handles it:** The Workflow node spawns a child run. The parent's run history sidebar exposes a "View sub-workflow run" button that navigates to the child workflow with the child run pre-selected. Child runs are labeled "Triggered by parent" and link back. You can drill in and out of any depth of agent hierarchy.

### Scenario 9: Parallel fan-out without merge errors

**Setup:** You parallel-fan-out 10 LLM calls to different providers, then merge their results in a single downstream node.

**Common failure pattern:** Naive graph executors hit conflict errors when two nodes return the same key with the default reducer. The fix is non-obvious. Reusing a "split in batches" node across multiple downstream nodes is typically documented as awkward and error-prone.

**How Symdue handles it:** Graph state is a `TypedDict` whose mutable fields use `Annotated` reducers (`merge_dicts`, `replace_list`). Parallel updates merge cleanly. The reducer choice is part of the substrate, not a per-workflow concern. We've eaten the broken glass; users don't pay it.

### Scenario 10: Provider-aware multimodal prompts without per-provider glue

**Setup:** Your workflow takes a screenshot URL and asks one model to describe it. You also want to A/B test against another vision model. The only difference between the two should be the model name.

**Common failure pattern:** Generic JS or Python interpolation `{{ var }}` substitutes strings. The AI nodes pass strings to provider SDKs but do not auto-route image URLs into provider-specific image content blocks. Image inputs require manually constructing the `messages` array per provider.

**How Symdue handles it:** `{node_name}` placeholders auto-detect the upstream output type. Image URLs are inserted at the placeholder's exact position as provider-specific image content blocks: OpenAI vision, Anthropic image, Gemini inline data, Perplexity, Ollama. Switching providers is changing the model name in a config field.

---

## §4: Architecture FAQ

### Why Temporal?

Three reasons:

1. **Crash-safe durability is automatic.** Workers can die and runs survive on history-event replay.
2. **Workflow/activity split.** The workflow stays lightweight and re-runnable while activities do the heavy work — including invoking Python nodes inside Docker containers.
3. **Primitives, not rebuild.** We get retries, heartbeats, signals, and timeouts as primitives instead of rebuilding them on Postgres + a queue.

Tradeoffs: Temporal adds an extra service to run (managed BYOC absorbs that cost), gRPC has a 4 MB payload limit (we worked around it with a `node_execution_history` table that gzip-compresses payloads), and there's more conceptual overhead than a simple job queue.

### Why LangGraph as the executor library?

We needed a typed-state graph executor with `Annotated` reducers for parallel fan-out, and writing that ourselves is months of work. We use LangGraph as a library only — no LangChain or LangSmith dependency in the hot path. If LangGraph's API changes, a manual topological-sort fallback path is already wired in `compiler.py`.

### What if Temporal is unavailable?

New runs can't start (the API returns 503-equivalent). In-flight runs continue to make progress until they need a heartbeat, then suspend. When Temporal recovers, suspended runs resume from their last persisted history event. Partial snapshots are already in Postgres so the canvas shows correct state.

### What if a node container crashes mid-execution?

The activity raises, Temporal's retry policy fires (exponential backoff, capped attempts). If retries exhaust, `_persist_partial_state_on_cancel` writes the partial snapshot, run status flips to `error`, and the user can resume from the failed node — skip-if-done preserves all upstream work.

### Per-node container isolation — what does that actually mean?

Every Python node executes in a fresh Docker container scoped to that node's run. The container ships only the explicitly declared `requirements` and the `storages` clients the NodeType requested — not the full server image. Concretely:

- A malicious or buggy Python node cannot read the host filesystem.
- It cannot see other tenants' env vars or other runs' state.
- It cannot escalate privileges to the worker process.
- Each run is a clean room.

This is a different security model from in-process workers where a Python step shares the host process with everything else.

### How does replay work?

Every node writes its output snapshot to a partial-state column on the run row after it completes. Resume reads that snapshot, replays the workflow as a Temporal workflow, and the skip-if-done predicate (`state["node_outputs"][node_id]` is present and not an error) skips any node that already has a successful output. You only re-run what doesn't have a result.

### Storage backends — how do they work?

A NodeType declares its storage dependencies in config: `"storages": ["minio", "postgres"]`. At runtime, the executor looks up the workspace's `StorageConfig` rows for those aliases (`default_minio`, `default_postgres`), instantiates a `StorageClient` per alias, copies the backend module + client into the node's Docker container, and injects a `storages` dict via `initialize(config, storages)`. The node's code is `storages["minio"].upload(...)` — credentials and connection details never appear in node code, and the same code runs in dev, staging, and prod with different `default_*` configs.

Six backends supported: MinIO/S3, Postgres, MongoDB, Redis, Chroma, local file.

### Which LLM providers are supported?

OpenAI, Anthropic, Gemini, Perplexity, Ollama out of the box. Bedrock, Vertex, and vLLM are mechanical to add (same `_format_message_for_provider` pattern in `executor.py`). All providers go through the same prompt-template syntax — switching providers is changing a model name.

### Is the workflow JSON portable?

Yes. Workflows export to JSON (nodes, connections, weights, source handles, configs, positions, metadata; credentials by alias only) and import via the API. The export format is stable across minor versions. Commit JSON to git alongside whatever Python NodeType code references it.

### Multi-tenancy?

Workspace = primary isolation boundary. Per-workspace storage configs, per-workspace LLM provider keys, per-workspace run history. Roadmap: per-workspace network egress controls, per-workspace Temporal namespaces.

---

## §5: Honest tradeoffs — what Symdue doesn't have yet

We deliberately publish the gaps. Buyers respect honesty more than they respect completeness theater.

### Integration count

Symdue day 1 ships eight built-in node types (Input, Custom Python, Custom LLM, Condition, Workflow, Workflow Template, Iterator, Wait). It does not ship hundreds of pre-built integration nodes for SaaS APIs.

This is a coverage problem, not an architecture problem. Each new integration is a Custom Python node template with `requirements` and `storages` declared — about 30 minutes of work per node for an experienced contributor. We're prioritizing the runtime first, integrations next. If your stack needs a specific integration, file an issue or send a PR; we'll merge fast.

### Template marketplace

A handful of starter kits ship with Symdue (research agent, lead qualification, customer support triage). A community template marketplace doesn't exist yet. Templates marketplace comes after we have ~20 in-house kits and a contribution flow.

### Form-rendering for end-users

Wait nodes can pause and resume on signals. They don't currently render forms or chat interfaces directly to end-users. To collect human input, today you point a Wait node at a webhook and have your own form / Slack button / email link hit that webhook. First-class form and chat trigger surfaces are roadmap.

### Mobile / tablet UX

The React canvas works on tablet but isn't optimized for mobile. If you need to monitor runs on a phone, the run history list is more usable than the canvas.

### Multi-tenant SaaS

Deliberate no-go. We don't share runtime between tenants because of the durability + isolation guarantees we make. Self-host, or use BYOC managed where we run Symdue on your own cloud account. There is no hosted public SaaS where your workflows run on infrastructure shared with strangers.

### Polished error UI / "click to debug"

The current debug surface is: open the run in the canvas → click the failed node → see inputs / outputs / error / traceback / container logs in the properties panel → "Resume from here" with adjusted config. Pause-and-resume + replay-from-node covers most production debugging needs. The per-error step-by-step inspection UX is less polished than what mature visual builders ship, and we'll get there.

### Auth / RBAC / SSO depth

Workspace-level isolation works today. Fine-grained RBAC (per-NodeType permissions, per-workflow read/write splits) and SSO via OIDC / SAML are roadmap features, typically delivered in the Cloud / Enterprise tier.

### Streaming UX in canvas

LLM responses can stream into the WebSocket envelope today. Whether the canvas renders partial tokens vs. final response is configurable but not consistent across all node types yet.

### Cost tracking dashboards

Per-call token + USD tracking is captured in the run snapshot. Aggregated dashboards (cost per workspace, cost per workflow over time) are not first-class yet.

### Brand, ecosystem, year-zero reality

Symdue is six weeks old in public. There are no Stack Overflow answers, YouTube tutorials, or third-party consulting agencies. The repo is your due diligence; the maintainers are reachable; the architecture is the bet. Apache 2.0 means the code outlives any single contributor.

---

## §6: Operational FAQ

### Logs?

Per-node container `stdout` / `stderr` are captured into the snapshot and exposed at `GET /api/runs/{workspace_id}/{run_id}/nodes/{node_id}/logs`. Aggregated worker logs go to the Docker Compose / Kubernetes standard sink. OpenTelemetry / Loki integration is on the roadmap.

### Metrics?

Temporal exposes Prometheus metrics out of the box. Per-workflow custom metrics emit through standard Temporal histograms.

### Retry policies?

Per-activity (Temporal): exponential backoff, capped attempts. Configurable per NodeType in node config.

### Timeouts?

Per-node activity timeout (default 600s for Python). Per-workflow run timeout (default 30 min). Wait nodes have their own `timeout_seconds`, capped at `max_wait_timeout_hours` (default 168h = one week).

### Backup / disaster recovery?

Postgres dump + Temporal namespace export. Workflow JSONs round-trip via export/import. A documented runbook ships in the deployment docs.

### Air-gapped deploys?

Yes — no cloud-only dependencies. `docker compose up` with an internal model-provider proxy works. Custom NodeTypes with `requirements` need an internal pip mirror.

### Worker layer language-agnostic?

Python today. Adding TypeScript / Go / Rust is mechanical because Docker is the boundary, but not shipped.

### Upgrade story?

Alembic migrations for the database. Temporal handles workflow-version pinning. The workflow JSON schema is versioned in the export payload. State lives in Postgres + Temporal, not in pickle files, so upgrade is a normal database migration — not a "delete your data and re-import" pattern.

---

## §7: When to use Symdue (and when not to)

The honest decision is which *category* of tool fits your stack. Tool categories below are described by their architectural pattern, not by product name.

### Tool categories at a glance

- **Hosted automation platform** — cloud SaaS, shared multi-tenant infra, hundreds of pre-built SaaS integrations, polished no-code UX, per-operation pricing. Optimized for trigger breadth + linear simplicity.
- **Self-hosted visual workflow platform** — open or source-available, large integration catalog, canvas editor, queue-based runtime, self-deployable. Optimized for breadth + UX maturity.
- **Code-first agent library** — Python or JS library, no canvas, state machines or graph executors in code, strong runtime semantics. Optimized for engineers who want everything in source control.
- **Symdue** — visual + Temporal-backed durable runtime + per-node container isolation + LLM-native primitives, Apache 2.0, self-hosted-first. Optimized for production AI workflows that need durability, audit, and a shared visual surface.

### When to pick which

Read each row and pick the column that matches your need. ✅ = strong fit, ⚠️ = partial / depends on tool, ❌ = not a fit.

| Your need | Hosted automation platform | Self-hosted visual workflow platform | Code-first agent library | **Symdue** |
|---|---|---|---|---|
| 100+ pre-built SaaS integrations day one | ✅ | ✅ | ❌ | ❌ (small set day-1, growing) |
| No-code authoring for non-engineers | ✅ | ✅ | ❌ | ⚠️ engineers-in-loop |
| Hosted SaaS, no infra to manage | ✅ | ⚠️ | ❌ | ❌ (self-host or managed BYOC) |
| Survives worker crash mid-run, no stuck-running rows | ❌ | ❌ | ⚠️ depends on library | ✅ Temporal-backed |
| Resume from arbitrary node, skip already-done work | ❌ | ❌ | ⚠️ partial / per-thread | ✅ skip-if-done |
| Long-running HITL pause that survives deploys | ❌ | ⚠️ often broken | ✅ varies | ✅ named-channel signals |
| Data stream → workflow with payload as inputs | ❌ DIY | ❌ DIY | ❌ DIY | ✅ queue-event runtime |
| Per-node container isolation (security / multi-tenant) | ❌ shared infra | ❌ shared process | ❌ same Python process | ✅ fresh Docker per node |
| Citation whitelist / fabricated-source dropping at runtime | ❌ DIY | ❌ DIY | ❌ DIY | ✅ substrate-level |
| Provider-aware multimodal prompts (image blocks per provider) | ❌ strings | ❌ strings | ⚠️ varies | ✅ |
| Replay-with-modified-inputs as an eval primitive | ❌ | ❌ | ⚠️ varies | ✅ |
| Refresh-safe canvas (close tab mid-run, come back, state survives) | ❌ | ❌ | N/A | ✅ |
| Apache 2.0, no internal-use-only or hosting restrictions | ⚠️ varies | ⚠️ many restrict commercial hosting | ✅ varies | ✅ |
| Same code dev → staging → prod, credentials swap automatically | ⚠️ per-app creds | ⚠️ manual promotion | ❌ DIY | ✅ storage-attached nodes |
| Mature template marketplace / community plugins day-1 | ✅ | ✅ | ⚠️ | ❌ (kits at launch, marketplace roadmap) |
| Form / chatbot UI for end-users | ✅ | ✅ | ❌ | ❌ (roadmap; webhook-out works today) |
| Years of YouTube tutorials and Stack Overflow answers | ✅ | ✅ | ✅ varies | ❌ (six weeks public) |

### Use Symdue when

- You're building production AI workflows that have to survive crashes, restarts, and long-running waits
- You need a graph that's also a live execution dashboard, not a separate observability tool
- You want non-engineers (PMs, ops, analysts) to read your workflow during incidents without learning Python
- You need replay-with-modified-inputs as a real eval primitive
- You need human-in-the-loop pauses that survive deploys
- You need data streams (Kafka, Redis Streams, webhooks) to fire workflows with the event payload as input
- You need per-node container isolation for security or multi-tenant reasons
- You want the same code to run in dev / staging / prod with different storage credentials, no code changes
- You ship LLM-driven workflows where hallucinated citations are a real risk

### Pick a different category when

- You need 300+ pre-built SaaS integration nodes on day one — pick a mature integration platform and accept the runtime tradeoffs
- You need a no-code tool for non-engineers to build workflows from scratch — Symdue assumes engineers in the loop
- You need a hosted public SaaS where your workflows run on shared infrastructure — that's not what Symdue offers
- You don't need durability — if your workflows are stateless transformations under 10 seconds, simpler tools work fine
- Your team's hard preference is code-first with no canvas — pick a code-first agent library and skip the visual surface

---

## §8: Getting started

### Quickstart

```bash
git clone https://github.com/vinodydev/symdue_oss
cd symdue_oss
cp server/.env.example server/.env
cd setup
docker compose up
```

Then open `http://localhost:3000`.

For non-Docker dev setup, see `setup/setup-mac.sh` and `setup/setup-db.sh`.

### Building your first workflow

Open the canvas → drag an Input node, a Custom LLM node, and an Iterator → wire them with edges → click Run → watch live status update node by node. See the demo workflows in `demos/` for concrete examples.

### Building your first agent

Agents in Symdue are workflows that loop. Pattern: a Planner LLM node that decides what to do next → tool nodes (web search, paper search, PDF read) that fan out from the plan → a Merge node that consolidates → an Analyzer LLM node that produces perspectives + open questions → a Condition node that exits if open questions are empty, else loops back to the Planner. This is the DEEP_RESEARCH demo workflow shipped in `demos/`.

### Where to ask questions

- **Bugs and feature requests:** [GitHub Issues](https://github.com/vinodydev/symdue_oss/issues)
- **Security disclosures:** see [SECURITY.md](../SECURITY.md)
- **General discussion:** [GitHub Discussions](https://github.com/vinodydev/symdue_oss/discussions) (once enabled)

---

## §9: License & governance

### Why AGPL v3 + Apache 2.0 SDK?

We picked this dual-license structure to balance OSS freedom with long-term commercial sustainability:

- **AGPL v3 on the runtime** prevents cloud hyperscalers from forking Symdue and reselling it as a competing managed service. Same protection model as Grafana and MongoDB.
- **Apache 2.0 on the plugin SDK** means custom NodeTypes you write are *separate works* — you license your NodeType code however you want, including proprietary. Same legal pattern as MySQL connectors (LGPL) or PostgreSQL extensions (BSD).
- **Apache 2.0 on demos** lets you copy and modify example workflows freely.

Self-hosting and internal use trigger zero AGPL obligations. Hosting unmodified Symdue for paying clients is fine (display "Source: [link]" notice, that's the whole obligation). API integration with Symdue from your application doesn't infect your application code (same as Postgres / Rails). Modifications to the runtime that are network-accessible to third parties trigger AGPL — for those use cases see [COMMERCIAL_LICENSE.md](../COMMERCIAL_LICENSE.md).

### Does AGPL apply to my use case?

| Your situation | License obligation |
|---|---|
| Self-hosting Symdue internally | None |
| Building custom NodeTypes against the Apache SDK | None |
| Authoring workflows | None — workflows are user content |
| Hosting unmodified Symdue for paying clients | Light — display "Source" notice |
| Modifying runtime, network-accessible to third parties | AGPL release source OR commercial license |
| Embedding Symdue code in closed-source commercial product | Commercial license |
| Running Symdue as managed-service competitor | Commercial license |

### Does AGPL apply to Symdue (the company) hosting Symdue Cloud?

No. AGPL is a permission grant from the copyright owner (Symdue the company) to other people. The owner isn't a licensee of their own code — we can host Symdue Cloud, add proprietary Cloud-only features, and serve paying customers without releasing source. Same pattern MongoDB Atlas, Grafana Cloud, Sentry SaaS use. Our CLA preserves this property as the contributor base grows.

### Do I need to sign a CLA to contribute?

For runtime contributions (AGPL'd code in `server/`, `client/`, `setup/`): yes. Sign once via CLA Assistant on your first PR. The CLA gives Symdue the right to relicense your contribution under commercial terms; you keep copyright. Standard practice for dual-licensed projects (Grafana, Sentry, HashiCorp, Cal.com all do this). See [CLA.md](../CLA.md).

For Apache 2.0 SDK / spec / demos contributions: no CLA needed. Just sign-off via DCO (`Signed-off-by: Your Name <email>` in commit messages).

### Is the runtime open-core or pure OSS?

Open-core. The runtime substrate is AGPL v3 (truly open, fork-able, self-hostable). Higher-level products built on top (Cloud, Enterprise tier features, specialized commercial offerings) are proprietary and live elsewhere. The runtime in this repo stays AGPL forever per [PRICING_PHILOSOPHY.md](../PRICING_PHILOSOPHY.md).

### Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md). Contributions are welcome — node types, integrations, bug fixes, doc improvements. We ship fast and review fast.

### What if you get hit by a bus?

AGPL v3 + the public commitment in [PRICING_PHILOSOPHY.md](../PRICING_PHILOSOPHY.md) mean the code outlives any single contributor. The architecture is composed of production-grade primitives (Temporal, Docker, Postgres, Redis) — not invented infrastructure. Anyone with a checkout can keep running their deployment indefinitely; anyone can fork the AGPL'd code and continue independently.
