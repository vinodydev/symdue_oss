# Troubleshooting

Self-diagnosis for the most common setup and runtime issues. Each entry has a
**symptom**, **what to check**, and **how to fix**. If your situation isn't
listed here, [open an issue](https://github.com/vinodydev/symdue_oss/issues).

---

## Canvas is stuck / WebSocket keeps disconnecting

### Symptom

- You open the workspace in the browser. The canvas loads.
- A run is supposedly active (sidebar shows `running` with a spinner) but no
  node ever turns green / blue / red.
- DevTools → Console may show repeated WebSocket connect → close cycles.
- Backend logs (`./symdue.sh logs backend`) show:
  ```
  ✅ WebSocket connected for workspace: <id>
  ⚠️  WebSocket error: Error -3 connecting to redis:6379. -3.
  ❌ WebSocket disconnected for workspace: <id>
  ```
  …repeating in a loop.
- Worker logs (`./symdue.sh logs temporal-worker`) show:
  ```
  Failed to publish node status: Error -3 connecting to redis:6379. -3.
  Failed to read pause flag for run …: Error -3 connecting to redis:6379.
  ```

### What's happening

`Error -3` is `EAI_AGAIN` from libc — **DNS resolution failed**. The backend
container is trying to resolve the docker service-name `redis` to an IP and
failing. Without Redis, no NODE_STATUS pub/sub events flow → WebSocket has
nothing to broadcast → canvas appears frozen.

The WebSocket itself is fine; Redis-name resolution is broken. There are two
typical root causes:

1. **Stale docker network state** from a previous compose project name,
   a partial `down`, or an orphan container with a conflicting hostname.
   The current backend container is on a network that doesn't have a
   working `redis` service-name entry. Most common.
2. **A different Redis is occupying host port 6379** (system Redis from
   `apt`, or an orphan container from another project) — preventing
   Symdue's own redis from starting at all.
3. **Docker daemon DNS is broken on the host** (after a network
   migration, VPN switch, or systemd-resolved hiccup).

### Fix — diagnose then act

#### Step 1: Check whether port 6379 has a conflicting process

```bash
sudo lsof -i :6379          # or: sudo ss -tlnp | grep 6379
```

You'll see one of three outcomes:

| Output | Meaning | What to do |
|---|---|---|
| **Nothing** (no output) | Port is free. Cause is stale network state — go to **Step 2** | — |
| `redis-server` (not in a container) | System Redis from `apt install redis-server` | `sudo systemctl stop redis-server && sudo systemctl disable redis-server`, **then Step 2** |
| `docker-proxy` pointing at a non-`graphmind-redis` container | Orphan Redis from another compose project | `docker ps -a \| grep redis`, `docker stop <container>` and `docker rm <container>`, **then Step 2** |
| Some other PID | Random process | `sudo kill <pid>`, **then Step 2** |

#### Step 2: Force-rebuild the stack

This is sufficient on its own for the vast majority of cases. It
performs `docker compose down -v --rmi local --remove-orphans`, rebuilds
images from scratch, and brings up a fresh network — which fixes stale
network state, orphan containers, and any cached-image weirdness in
one shot.

> ⚠️ This deletes named docker volumes — your runs, workspaces, and
> uploaded files will be lost. If you have data you care about, back
> up the postgres volume first. For dev / first-run / "nothing
> persistent yet" setups, just go ahead.

```bash
cd flowgraph_oss/setup
./symdue.sh rebuild --force      # --force skips the y/N prompt
```

> **Why not just `./symdue.sh restart`?** `restart` does
> `docker compose restart` — it reuses existing containers and
> network. It won't clean up orphans or stale DNS state. `rebuild`
> is the right tool for this specific class of problem.

After rebuild, hard-refresh the browser and try a run. If WebSocket
works, you're done — stop here. If it still fails, continue.

#### Step 3: Verify DNS resolution from inside the backend container

```bash
docker exec graphmind-backend python -c "import socket; print(socket.gethostbyname('redis'))"
```

Expected: `172.19.0.X` (or similar). If this errors out after a clean
rebuild, the host's Docker daemon DNS is broken — go to Step 4.

#### Step 4: Pin Docker daemon DNS to public resolvers

```bash
sudo bash -c 'cat > /etc/docker/daemon.json' <<'JSON'
{ "dns": ["1.1.1.1", "8.8.8.8"] }
JSON
sudo systemctl restart docker
cd flowgraph_oss/setup
./symdue.sh rebuild --force
```

This survives reboot and fixes about 95% of stubborn EAI_AGAIN cases
(same fix that resolves the
[yarn-install DNS issue](#yarn-install-fails-with-eai_again-during-docker-build)).

#### Step 5: Nuclear network prune (only if Steps 1–4 don't work)

```bash
cd flowgraph_oss/setup
./symdue.sh stop
docker network prune -f          # symdue.sh doesn't expose this yet
./symdue.sh rebuild --force
```

---

## "Redis port is already in use" when starting Symdue

### Symptom

`./setup/symdue.sh start` errors with:

```
Error response from daemon: Ports are not available: exposing port TCP 0.0.0.0:6379
…address already in use
```

### What's happening

The compose file binds host port 6379 → redis container. Something else on the
host is already on that port — usually system Redis or an orphan container.

### Fix

Same flow as the canvas-stuck section above:

```bash
sudo lsof -i :6379
```

Stop whatever's on it (system service or orphan container — see the table in
[Step 1](#step-1-check-whether-port-6379-has-a-conflicting-process)), then:

```bash
cd flowgraph_oss/setup
./symdue.sh rebuild --force
```

If you can't free 6379 for some reason (another app legitimately needs it), set
a different host port for Symdue's redis in `server/.env`:

```bash
REDIS_PORT=6390   # any free port
```

The Symdue stack itself uses `redis:6379` *inside* the docker network — only
the host-side mapping changes. After editing `.env`, rerun
`./symdue.sh rebuild --force`.

---

## Yarn install fails with `EAI_AGAIN` during docker build

### Symptom

`./setup/symdue.sh start` (or a `./setup/symdue.sh rebuild` on first run) fails with:

```
[frontend 6/8] RUN yarn install
error Error: getaddrinfo EAI_AGAIN registry.yarnpkg.com
```

### What's happening

Transient DNS failure during BuildKit's parallel image build. Yarn v1 doesn't
retry DNS errors and aborts the entire install if even one of its ~150
concurrent package resolutions hiccups.

### Fix

#### 1. Retry once

Most EAI_AGAIN incidents resolve on retry:

```bash
cd flowgraph_oss/setup
./symdue.sh start
```

If you need to specifically rebuild *just* the frontend image (avoiding
parallel DNS pressure from rebuilding all services at once), `symdue.sh`
doesn't expose a single-service rebuild yet, so drop to raw docker compose
for this one step:

```bash
cd flowgraph_oss/setup
docker compose build frontend
./symdue.sh start
```

#### 2. If retry fails, pin Docker to public DNS

```bash
sudo bash -c 'cat > /etc/docker/daemon.json' <<'JSON'
{ "dns": ["1.1.1.1", "8.8.8.8"] }
JSON
sudo systemctl restart docker
```

Then rebuild.

---

## "LLM config 'bc8e27a0-…' not found or deleted"

### Symptom

A node in the demo workflow (DEEP_RESEARCH or similar) errors with:

```
ValueError: LLM config 'bc8e27a0-4031-4d89-8f1a-2ea18855eecf' not found or deleted
```

### What's happening

The exported demo workflow JSONs reference LLM config UUIDs from the
demo-creator's database. On a fresh install you have your own UUIDs, so the
references don't resolve.

### Fix

1. Open Symdue at http://localhost:3000.
2. Settings → LLM Configs → **+ Add Config**. Plug in your provider key
   (Gemini, OpenAI, Anthropic, Ollama, etc.).
3. Open the demo workflow → click each LLM node → in the right-hand properties
   panel, change **LLM Config** dropdown to your newly-created config.
4. Save (auto-saves on selection change).

You'll need to do this once per LLM node in each demo. Self-built workflows
won't hit this — they pick up your configs at creation time.

---

## "Recursion limit of 10007 reached without hitting a stop condition"

### Symptom

A run errors with:

```
Caused by: GraphRecursionError: Recursion limit of 10007 reached without
hitting a stop condition. You can increase the limit by setting the
`recursion_limit` config key.
```

### What's happening

LangGraph's internal step counter exceeded the limit because the workflow's
loop never terminated. The most common culprit in iterative workflows
(DEEP_RESEARCH-style) is an EXIT_GATE / MAX_ITERATIONS condition that never
evaluates true — usually because the comparison inputs are empty or wrongly
typed.

### Fix

1. Inspect the failing run's snapshot in the run-history sidebar. Check
   `_step_count` and the loop's gate node output.
2. Verify the EXIT_GATE / MAX_ITERATIONS node:
   - Is the iteration counter incrementing on each loop pass?
   - Is the maximum value set sensibly (typically 3–5 for most agents)?
   - Does the gate's condition expression actually evaluate to true at the
     limit? (Common bug: comparing strings with `>=` instead of `==`.)
3. If you control the workflow, fix the gate's logic and re-run.
4. If you're running a community-shared workflow, this is a workflow-author
   bug — flag it on the source repo / discussion thread.

---

## Backend logs show "database 'graphmind' does not exist" every 10 seconds

### Symptom

Postgres logs (`./symdue.sh logs postgres`) repeatedly show:

```
2026-05-09 06:04:32 UTC [67] FATAL:  database "graphmind" does not exist
```

…every 10 seconds.

### What's happening

This is **harmless log noise**. Temporal's bootstrap probes the postgres
server with the connection user (`graphmind`) as a default database name
before it switches to its own `temporal` and `temporal_visibility` databases.
Postgres logs the failed probe at `FATAL` severity even though Temporal
recovers immediately.

### Fix

None — backend works fine; Temporal works fine. The error log is cosmetic.
You can ignore it. (If you'd like Symdue to suppress it, file an issue.)

---

## Workflow keeps running after I click Pause and ends in `CancelledError`

This was a real bug fixed in commit `ecf1100` (May 2026). If you're on a
Symdue version before that commit, update:

```bash
git pull
./setup/symdue.sh restart
```

After update, Pause halts the workflow at the next LangGraph chunk boundary
(within ~1 sec for fast nodes; up to one in-flight LLM-call duration for
slow nodes). No more spurious CancelledError on resumed runs.

---

## Canvas shows wrong / stale state after a stack restart

Same situation: bug fixed in commit `ecf1100`. WebSocket reconnect now
re-fetches the active run's full snapshot and forces the canvas to repaint,
catching up on any NODE_STATUS events that were dropped during the
disconnect window. If you're on an older commit, `git pull` and restart.

---

## Where to ask for help

- **GitHub Issues**: <https://github.com/vinodydev/symdue_oss/issues> for
  bugs, regressions, and feature requests.
- **Discord**: <https://discord.gg/c3ysHGCyqs> for setup help, real-time
  questions, and workflow-design discussions.
- **Security disclosures**: see [SECURITY.md](../SECURITY.md).

When filing a setup issue, please include:

1. Output of `./symdue.sh status` (which services are healthy / unhealthy).
2. Last ~50 lines of `./symdue.sh logs backend` and `./symdue.sh logs
   temporal-worker`.
3. Output of `sudo lsof -i :6379` (in case it's another Redis port issue).
4. Your OS / Docker version (`docker --version`, `uname -a`).
