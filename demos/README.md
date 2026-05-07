# Demo workflows

Workflow exports used to film the launch demos. Import any `.json` here via the workflow import button in the symdue UI, then assign your LLM provider config — `configId` is left empty on purpose so the import doesn't depend on a UUID that exists only on our machine.

## hn-daily-digest.json

Fetches the top 10 Hacker News stories, summarizes each with its top comments, and composes a daily digest. ~3-minute runtime. No auth required — uses the public HN Firebase API.

**Shape:** `FETCH_HN_STORIES` → `FETCH_STORY_DETAILS` (iterator) → `SUMMARIZE_STORY` (iterator) → `DAILY_DIGEST`

Used in the following demos:

- **Plug Pull** — kick off the run, kill the backend container during iteration, restart, watch it finish from where it stopped.
- **Prompt Rewind** — run once with the default `SUMMARIZE_STORY` prompt; then click step 3, sharpen the prompt, replay forward. Steps 1–2 stay cached.
- **100-Item Microscope** — the iterator over 10 stories shows a strip of per-iteration nodes. Click any one to see exact input, exact prompt, exact output.
- **Prompt Bisect** — keep a saved run, change the `SUMMARIZE_STORY` prompt, replay against the saved upstream. See the diff.

### Post-import setup

1. Set the LLM provider `configId` on `SUMMARIZE_STORY` and `DAILY_DIGEST` (any provider works; demo was filmed against Claude).
2. (Optional) Adjust the `[:10]` slice in `FETCH_HN_STORIES` for a longer or shorter run.

## local-file-summarizer.json

Walks a directory of local files (`.txt`, `.md`, `.log`, `.rst`), splits each into 1500-token chunks via `tiktoken`, summarizes the chunks with an LLM, rolls up per file, and synthesizes a final HTML report rendered inline. Combines a back-edge loop (file iteration) with an iterator (chunk parallelism within a file).

**Shape:** `LIST_FILES → LOAD_NEXT → SUMMARIZE_CHUNK (iterator) → ROLLUP → GATE` with `GATE ─false→ LOAD_NEXT` (loop) and `GATE ─true→ FINAL_REPORT → PREVIEW`.

Setup is more involved than `hn-daily-digest` because the workflow reads from the host filesystem — see [`local-file-summarizer.md`](local-file-summarizer.md) for where to drop files (`<repo-parent>/graph_mind/storage/inputs/` — shared across all workspaces, no UUID in the path), the one-time DooD path fix in `docker-compose.yml`, and the customization points (chunk size, file extensions, scan directory).

Used to demo:

- **The loop primitive** — back-edge from a `condition-python` node, self-state via `inputs[<own_name>]`, `MAX_GRAPH_STEPS` termination.
- **The `files` helper** — sandboxed local-FS reads (`/workspace/files/`) without configuring a storage backend.
- **Iterator + loop composition** — outer loop over files, inner iterator over chunks per file.
- **HTML viewer terminal** — sandboxed iframe rendering of an LLM-emitted report.
