# Local File Summarizer

A workflow that walks a directory of local files, splits each file into token-bounded chunks, summarizes the chunks with an LLM, rolls them up per file, and synthesizes a final HTML report.

**Architecture (the loop is the interesting part):**

```
            ┌─────────────────────────────────────────────────────┐
            │                  back-edge (false branch)           │
            ↓                                                     │
LIST_FILES ─→ LOAD_NEXT ─→ SUMMARIZE_CHUNK ─→ ROLLUP ─→ GATE ─────┘
                          (iterator: chunks)                  │
                                                              │ true
                                                              ↓
                                                        FINAL_REPORT ─→ PREVIEW
```

- **Outer loop** (sequential): one pass per file. `LOAD_NEXT` advances an index across the file list; `GATE` decides exit-or-continue.
- **Inner iterator** (parallel): within a single pass, `SUMMARIZE_CHUNK` fans out across that file's chunks.
- **Self-state**: both `LOAD_NEXT` and `ROLLUP` read `inputs[<own_name>]` to carry state across loop passes (per Symdue's loop semantics — see [`docs/`](../docs/)).

---

## File setup — where to drop files on the host

This workflow reads from `/storage/inputs/` inside the sandbox — that path is bind-mounted from a single host directory and is **shared across all workspaces**, so you don't need to know any workspace UUIDs to drop files.

```
                          HOST FILESYSTEM
  <repo-parent>/graph_mind/storage/inputs/  ←── you drop files here
                 │
                 │ (DooD bind-mount when spawning sandbox)
                 ↓
  SANDBOX CONTAINER:    /storage/inputs/    ←── what your Python node sees (read-only)
```

Symdue uses Docker-out-of-Docker (DooD): the backend container asks the **host** docker daemon to spawn each sandbox container, so bind-mount source paths must resolve on the host filesystem.

### Step 1 — create the host directory

If you ran `setup/setup-dood.sh` (or `setup-mac.sh`), the parent directory already exists at `<parent-of-flowgraph_oss>/graph_mind/storage/`. Just add the `inputs/` subdir:

```sh
# from anywhere
mkdir -p "$(realpath <repo-parent>)/graph_mind/storage/inputs"
```

Concrete example, if you cloned `flowgraph_oss` into `~/code/`:

```sh
mkdir -p ~/code/graph_mind/storage/inputs
```

### Step 2 — resolve the DooD path mismatch (once, per deployment)

There's a gotcha: `setup/docker-compose.yml:115` ships with `HOST_STORAGE_ROOT: /storage` — the literal string `/storage`, **not** the real host path that `setup-dood.sh` creates. The DooD bind-mount source has to resolve on the host, so you need to fix this once. Pick one option:

**Option A (recommended) — point `HOST_STORAGE_ROOT` at the real path.**

Edit `setup/docker-compose.yml`. In **both** the `backend:` and `temporal-worker:` services, replace:

```yaml
HOST_STORAGE_ROOT: /storage
```

with the absolute path:

```yaml
HOST_STORAGE_ROOT: /home/you/code/graph_mind/storage
```

(use whatever `realpath <repo-parent>/graph_mind/storage` prints). Then:

```sh
docker compose -f setup/docker-compose.yml up -d
```

**Option B — symlink `/storage` to the real path.**

```sh
sudo ln -s "$(realpath <repo-parent>/graph_mind/storage)" /storage
```

Now the literal `/storage` path in compose resolves correctly on the host. No compose edit needed.

### Step 3 — drop your files

```sh
cp /path/to/your/notes/*.md ~/code/graph_mind/storage/inputs/
```

Supported extensions out of the box: `.txt`, `.md`, `.markdown`, `.log`, `.rst`. Add more in `LIST_FILES`'s `ALLOWED_EXTS` if needed.

That's it — no upload step, no API call, no workspace ID. Run the workflow; `LIST_FILES` discovers everything.

### Verifying the bind-mount actually attached

If `LIST_FILES` returns `{"error": "/storage/inputs does not exist..."}`, the bind-mount didn't attach. Quick checks:

```sh
# 1. Confirm the host path exists and has your files
ls -la <repo-parent>/graph_mind/storage/inputs/

# 2. Confirm HOST_STORAGE_ROOT inside the backend container points at a real host path
docker compose -f setup/docker-compose.yml exec backend env | grep HOST_STORAGE_ROOT

# 3. Spawn a one-off sandbox and check the mount manually (run this on the HOST)
docker run --rm -v "<the-HOST_STORAGE_ROOT-value>:/storage:ro" \
    python:3.11-slim ls -la /storage/inputs
```

If step 3 lists your files but the workflow doesn't see them, restart the backend so the new env vars take effect: `docker compose restart backend temporal-worker`.

### Three places files can come from — and when to use each

| Mount / mechanism          | Host path (default)                                       | Mode | Scope             | Use when                                                                |
|----------------------------|-----------------------------------------------------------|------|-------------------|-------------------------------------------------------------------------|
| `/storage/` (this demo)    | `<repo-parent>/graph_mind/storage/`                       | ro   | shared all-WS     | "I have files I want to feed in." Simple, no workspace UUID in the path.|
| `/workspace/files/`        | `<repo-parent>/graph_mind/workspaces/<workspace_id>/files/` | rw   | per-workspace     | Per-workspace isolation, or the node needs to write files back.         |
| `storages["minio"]` etc.   | (configured per-workspace)                                | rw   | configured        | Files produced/consumed *at runtime* via a storage backend (S3, Postgres, etc.). |

We picked `/storage/` for this demo because the workflow is "summarize this folder of files" — read-only is sufficient, and skipping the workspace-UUID path is friendlier for first-time setup. To switch to per-workspace isolation, change `SCAN_DIR` in `LIST_FILES` to `'/workspace/files/inputs'` and create the directory at `<repo-parent>/graph_mind/workspaces/<workspace_id>/files/inputs/` instead.

---

## Post-import setup

1. **Set the LLM provider `configId`** on `SUMMARIZE_CHUNK` and `FINAL_REPORT` (any provider works — Claude, OpenAI, Gemini, Ollama, Perplexity).
2. **Verify `HOST_WORKSPACE_ROOT`** is set on the backend container. Without it, `/workspace/files/` won't be bind-mounted and `LIST_FILES` will report the missing-directory error.
3. **Drop your files** into `${HOST_WORKSPACE_ROOT}/<workspace_id>/files/inputs/`.
4. **Run the workflow.** No input parameters needed — `LIST_FILES` discovers everything.

---

## Customization points

### Chunk size (`LOAD_NEXT`)

Top of the script:

```python
CHUNK_TOKENS = 1500   # max tokens per chunk
OVERLAP = 150         # tokens shared between adjacent chunks (preserves context across boundaries)
```

Smaller chunks → more LLM calls (more cost, slower) but tighter per-chunk summaries. Larger chunks → fewer calls but the LLM may dilute detail. 1500/150 is a reasonable starting point for most LLMs (well under any provider's input limit, leaves headroom for the prompt).

The token count uses `tiktoken`'s `cl100k_base` encoding (GPT-4 / o200k-compatible). It's *approximate* for non-OpenAI providers but close enough for chunk sizing — Anthropic's tokenizer is within ~10% on English text.

### File extensions (`LIST_FILES`)

```python
ALLOWED_EXTS = ('.txt', '.md', '.markdown', '.log', '.rst')
```

Add `.html`, `.json`, `.csv`, etc. if you want them included. Keep in mind these are read as text — binaries will produce garbage.

### Scan directory (`LIST_FILES`)

```python
SCAN_DIR = '/workspace/files/inputs'
```

Switch to `/storage/some-fixture-set/` if you've configured `HOST_STORAGE_ROOT` and want to summarize a shared, read-only fixture set instead.

### Final report format (`FINAL_REPORT`)

The prompt asks for sandboxed-safe HTML so the `PREVIEW` node renders it inline. Switch to markdown if you'd rather copy/paste the output — but then drop or replace the `PREVIEW` node, since it expects HTML.

---

## Why a back-edge loop instead of a single iterator over all files?

You could fan out across all files in parallel by stacking iterators (one over files, then another over chunks). It would be faster. Two reasons this demo uses a sequential loop instead:

1. **It demonstrates the loop primitive.** Symdue supports back-edge loops with cycle detection and a `MAX_GRAPH_STEPS` bound (default 1000) — and that's worth showing in a demo workflow.
2. **Cost control.** Sequential lets you watch the running summary build up and `Cancel` mid-run if early files reveal the topic isn't what you expected. A parallel fan-out commits to all the LLM calls upfront.

For pure speed on a small known set of files, swap to a flat iterator pipeline; for arbitrary or large folders where you want graceful early-exit, keep the loop.

---

## Loop bounds

Each pass through the loop counts as **one pass per file** plus the in-pass nodes (`LOAD_NEXT`, `SUMMARIZE_CHUNK`, `ROLLUP`, `GATE`) — so ~4-5 step counter increments per file. With the default `MAX_GRAPH_STEPS=1000`, you can summarize ~200 files in one run before hitting the bound. To go higher, raise `MAX_GRAPH_STEPS` on the backend (env var, not in the workflow JSON).

---

## Files this demo touches

- `/workspace/files/inputs/*.{txt,md,log,rst,markdown}` — your input files (you drop them).
- No storage backends required.
- No external network calls except the LLM API.
