/**
 * Starter code injected into a brand-new Custom Python node's editor.
 *
 * Surfaces the three things that aren't obvious from an empty editor:
 *   1. The supported `def main(inputs, storages, files)` signature.
 *   2. The four sandbox mount points that `files` can read from.
 *   3. The configured-storage backends accessible via `storages[alias]`.
 *
 * Single source of truth — also re-importable by a future "Reset to template"
 * action in the Properties panel, or by a multi-template picker.
 *
 * If a future backend deploy seeds a non-empty `default_config.code` on the
 * `custom-python` NodeType, the merge in NodeModal.tsx defers to the backend
 * value and skips this template. So this is a frontend fallback, not the
 * canonical default.
 */
export const PYTHON_NODE_TEMPLATE = `"""
Custom Python node — your code runs in a fresh sandbox container.

Define \`main(inputs, storages, files)\` and return any JSON-serializable
value. All three parameters are optional: the simplest valid node is
    def main(inputs): return inputs
which passes upstream data through unchanged.
"""


def main(inputs, storages, files):
    # ────────────────────────────────────────────────────────────────────────
    # inputs — dict of upstream node outputs, keyed by upstream node NAME.
    # Connect a node called "Fetcher" into this one; access it as
    #     inputs["Fetcher"]
    # ────────────────────────────────────────────────────────────────────────
    upstream = inputs

    # ────────────────────────────────────────────────────────────────────────
    # files — zero-config local-FS reads. Four sandbox mount points:
    #     /workspace/files/   rw   per-workspace, persists across runs
    #     /storage/           ro   shared storage (writes go via storages)
    #     /cache/             rw   pip + intermediate scratch
    #     /tmp/               rw   per-run scratch, dies with the container
    #
    # All methods raise PermissionError if the path resolves outside those
    # four roots — no /etc/passwd, no /home, no surprises.
    #
    #   files.read_text(path)              → str   (utf-8 by default)
    #   files.read_bytes(path)             → bytes (binary blobs, images)
    #   files.read_json(path)              → parsed JSON (dict / list / etc.)
    #   files.read_csv(path)               → list[dict] (header row, no pandas)
    #   files.list_dir(path, suffix="")    → sorted list[str] of file paths
    #   files.exists(path)                 → bool (False if outside SAFE_ROOTS)
    # ────────────────────────────────────────────────────────────────────────
    # config = files.read_json("/workspace/files/config.json")
    # rows   = files.read_csv("/workspace/files/orders.csv")
    # for path in files.list_dir("/workspace/files/inbox/", suffix=".json"):
    #     item = files.read_json(path)
    #     ...
    # if files.exists("/workspace/files/optional.txt"):
    #     extra = files.read_text("/workspace/files/optional.txt")

    # ────────────────────────────────────────────────────────────────────────
    # storages — configured backends, aliased per-node in this node's
    # Properties → "Storages" section. Same .get() / .put() / .list() /
    # .delete() shape across every backend type:
    #     postgresql / redis / mongodb / chroma / minio / local_file
    #     gdrive (planned)
    # ────────────────────────────────────────────────────────────────────────
    # cached = storages["redis"].get("key")
    # storages["pg"].put("user:42", {"name": "Alice"})
    # storages["minio"].put("results/run42.json", b'{"x": 1}')
    # for key in storages["mongo"].list(prefix="run_"):
    #     ...

    # ────────────────────────────────────────────────────────────────────────
    # Do the work. Return any JSON-serializable value — that becomes this
    # node's output and feeds downstream connected nodes.
    # ────────────────────────────────────────────────────────────────────────
    return {"echo": upstream}
`;
