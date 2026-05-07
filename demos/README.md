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
