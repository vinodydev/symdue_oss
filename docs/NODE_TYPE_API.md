# Symdue NodeType Plugin API

Stable public contract for custom NodeType authors. Versioned with semantic versioning. Backwards compatible within major versions.

**Current API version: 1.0.0** (released with Symdue 0.1.0-agpl, May 2026)

## License of this document and the API surface it describes

The NodeType API spec, schemas (`server/schemas/node_type.py`, `server/schemas/node.py`, `server/schemas/edge.py`, `server/schemas/workflow.py`, `server/schemas/storage.py`, `server/schemas/event.py`, `server/schemas/signal.py`, `server/schemas/run.py`, `server/schemas/llm_config.py`), and example NodeTypes in `demos/` are licensed under the **Apache License 2.0**.

Custom NodeTypes you write against this API are **separate works** under AGPL doctrine — they are not derivative works of the AGPL'd Symdue runtime. You may license your custom NodeType code however you wish, including proprietary licensing.

This license boundary follows established legal precedent:
- **PostgreSQL extensions** (BSD core + BSD extension API → proprietary extensions like pgvector, TimescaleDB, Citus distribute under various licenses)
- **MySQL connectors** (GPL core + LGPL connectors → see [MySQL FOSS License Exception](https://www.mysql.com/about/legal/licensing/foss-exception/))
- **Linux kernel** (GPL core + `EXPORT_SYMBOL` boundary marking → proprietary kernel modules like NVIDIA's are widely shipped)
- **WordPress** (GPL core + plugins/themes can be proprietary in practice)

## API stability commitment

Symdue commits to:

1. **Backwards compatibility within major versions.** A NodeType built against API v1.0.0 will continue to work under all v1.x.x runtime versions.
2. **12-month deprecation period** for any breaking change. v2.0.0 will not be released without 12 months' notice during which v1.x.x continues to be supported in v2.x.x runtime.
3. **Semantic versioning** for the API (separate from runtime version, though typically aligned at major versions):
   - `1.0.x`: bug fixes only, no new fields, no behavior changes
   - `1.x.0`: new fields with sensible defaults, additional lifecycle hooks, expanded protocols (backwards-compatible)
   - `2.x.x`: breaking changes (after 12-month deprecation period of `1.x` features)
4. **Stable schema field names.** Once a field is documented in the API, we will not rename, remove, or change its semantics within a major version.

## Quick start: a custom NodeType in 30 lines

The minimal custom Python NodeType skeleton:

```python
# my_custom_node.py
# SPDX-License-Identifier: <YOUR-CHOICE>  # e.g., "Apache-2.0", "MIT", "Proprietary"

def initialize(config: dict, storages: dict) -> dict:
    """
    Called once per node-type instance when the NodeType is registered.
    Use this to validate configuration and prepare any persistent state.

    Args:
        config: NodeType-instance configuration (from the canvas / workflow).
        storages: Dict of StorageClient instances declared by this NodeType.

    Returns:
        Dict that will be passed back as `state` in subsequent calls.
    """
    return {"initialized": True}


def handle(inputs: dict, config: dict, storages: dict, state: dict) -> dict:
    """
    Called per workflow run when this node executes.

    Args:
        inputs: Dict of input port name → value (from upstream nodes).
        config: NodeType-instance configuration (current values).
        storages: Dict of StorageClient instances.
        state: State dict returned by `initialize()`.

    Returns:
        Dict of output port name → value. Will be passed to downstream nodes.
    """
    # Your logic here
    result = {"output": inputs.get("input", "") + "!"}
    return result


# That's the entire required surface. Optional hooks below.
```

Register the NodeType via the API:

```python
# Via Symdue REST API
POST /api/workspaces/{workspace_id}/node-types
{
    "name": "my-custom-node",
    "description": "Adds an exclamation mark",
    "category": "Custom",
    "default_config": {},
    "config_schema": {
        "type": "object",
        "properties": {}
    },
    "input_ports": [{"name": "input", "type": "string"}],
    "output_ports": [{"name": "output", "type": "string"}]
}
```

## NodeType lifecycle

1. **Registration** — NodeType is registered with Symdue runtime via REST API or pre-loaded NodeType definition files.
2. **Configuration** — User authors a workflow that includes a node of this NodeType, configures it via the canvas.
3. **Initialization** — When the workflow runs, `initialize(config, storages)` is called once per node instance to set up state.
4. **Execution** — `handle(inputs, config, storages, state)` is called when the workflow execution reaches this node.
5. **Cleanup** — `cleanup(state)` is called on container teardown (optional hook).

## Required interface

The minimum a custom NodeType must implement:

```python
def handle(inputs: dict, config: dict, storages: dict, state: dict) -> dict
```

This is the only required function. All other lifecycle hooks are optional.

## Optional lifecycle hooks

```python
def initialize(config: dict, storages: dict) -> dict:
    """Called once before first execution. Returns initial state dict."""

def cleanup(state: dict) -> None:
    """Called on container teardown. Use for resource cleanup."""

def health_check(state: dict) -> bool:
    """Called periodically to verify NodeType health. Returns True if healthy."""
```

## Inputs and outputs schema

NodeTypes declare their input and output ports in their registration data:

```json
{
    "input_ports": [
        {"name": "user_query", "type": "string", "required": true},
        {"name": "context", "type": "object", "required": false, "default": {}}
    ],
    "output_ports": [
        {"name": "result", "type": "string"},
        {"name": "metadata", "type": "object"}
    ]
}
```

Supported port types in v1.0:
- `string`, `int`, `float`, `bool`
- `object` (arbitrary JSON object)
- `array` (arbitrary JSON array)
- `image_url` (URL to an image, auto-routed to provider-specific image content blocks for downstream LLM nodes)
- `binary` (base64-encoded binary data)

Custom types beyond these are stored as `object` and passed through.

## Configuration schema

NodeType configuration is defined as JSON Schema:

```json
{
    "config_schema": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "enum": ["openai/gpt-4o", "anthropic/claude-3.5-sonnet"],
                "default": "openai/gpt-4o"
            },
            "temperature": {
                "type": "number",
                "minimum": 0,
                "maximum": 2,
                "default": 0.7
            }
        },
        "required": ["model"]
    },
    "default_config": {
        "model": "openai/gpt-4o",
        "temperature": 0.7
    }
}
```

The Symdue canvas auto-generates a configuration form from this schema.

## Storages dict

NodeTypes declare which storage backends they need access to:

```json
{
    "storages": ["postgres", "minio", "chroma"]
}
```

At runtime, the `storages` dict passed to `initialize()` and `handle()` contains pre-configured `StorageClient` instances:

```python
def handle(inputs, config, storages, state):
    # Postgres SQL operations
    storages["postgres"].execute("INSERT INTO logs (msg) VALUES (%s)", inputs["msg"])
    
    # MinIO/S3 object upload
    storages["minio"].upload("bucket/key", binary_data)
    
    # Chroma vector search
    results = storages["chroma"].similarity_search("query", limit=10)
    
    return {"output": "done"}
```

The runtime resolves which actual storage instance is connected to each alias per workspace (e.g., `default_postgres` → workspace-specific Postgres connection). This allows the same NodeType code to run unchanged across dev / staging / prod with different storage credentials.

Storage interface declarations are in `server/schemas/storage.py` (Apache 2.0 licensed).

## Error semantics

NodeTypes report errors by raising Python exceptions. The Symdue runtime:
- Catches the exception
- Records the traceback in the run history
- Marks the node status as `error`
- Triggers Temporal's retry policy (configurable per NodeType: max attempts, exponential backoff)
- If all retries exhausted, persists partial state and surfaces the error to the canvas

```python
def handle(inputs, config, storages, state):
    if not inputs.get("required_field"):
        raise ValueError("required_field is missing")
    # ...
```

For non-retryable errors, raise a custom exception class (the runtime treats `ValueError` as retryable by default; subclassing `Exception` directly is treated as non-retryable):

```python
class NonRetryableError(Exception):
    """Marker exception — runtime will not retry."""
    pass

def handle(inputs, config, storages, state):
    if "fatal_condition" in inputs:
        raise NonRetryableError("This run cannot succeed; fail fast")
```

## Communication contract

Per-node communication between the Symdue runtime and a custom NodeType is via:

1. **Function arguments** — `inputs`, `config`, `storages`, `state` dicts passed to `handle()`
2. **Return value** — dict of output port name → value
3. **Exception raises** — for error reporting

The NodeType runs in a **fresh Docker container per node execution**. Communication is via:
- Initial input JSON injected as environment variables / file mount
- Output JSON written to a known file path (handled by the runtime, not the NodeType author)
- Storages dict pre-resolved by the runtime; NodeType code just calls methods on it

The NodeType **does not** need to manage:
- Container lifecycle
- Process management
- Inter-node communication (the runtime handles routing)
- Persistence / replay (the runtime handles snapshot-per-node)

## Versioning policy in detail

### v1.0.0 stable contract (current)

These are the **stable, committed** elements of the API:

- The function signatures of `initialize`, `handle`, `cleanup`, `health_check`
- The structure of `inputs`, `config`, `storages`, `state` dicts
- The supported port types
- The `config_schema` JSON Schema format
- The error-handling semantics (exception → retry → partial-state-on-cancel)
- The storages dict resolution (workspace-scoped, alias-based)

### What may change in v1.x.x (backwards-compatible additions)

- New optional lifecycle hooks
- New port types (e.g., `audio_url`, `video_url`)
- New StorageClient methods (existing methods stay)
- New optional fields in NodeType registration schema
- New event/signal hooks

### What requires v2.0.0 (breaking changes, 12-month deprecation)

- Renaming or removing existing function arguments
- Changing the return type semantics of `handle`
- Removing supported port types
- Changing the storages dict resolution model

## Examples

### Example 1: Simple text-transformation NodeType (Apache 2.0)

```python
# uppercase_node.py
# SPDX-License-Identifier: Apache-2.0

def handle(inputs, config, storages, state):
    text = inputs.get("text", "")
    return {"result": text.upper()}
```

### Example 2: LLM-calling NodeType (proprietary — your choice)

```python
# my_proprietary_summarizer.py
# SPDX-License-Identifier: Proprietary
# Copyright (c) 2026 Your Company. All rights reserved.

import openai

def initialize(config, storages):
    client = openai.OpenAI(api_key=config["api_key"])
    return {"client": client}

def handle(inputs, config, storages, state):
    response = state["client"].chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": "Summarize concisely."},
            {"role": "user", "content": inputs["text"]}
        ]
    )
    return {"summary": response.choices[0].message.content}
```

This NodeType is fully proprietary — not AGPL-bound — because it's built against the Apache 2.0 SDK API surface and runs as a separate Docker container.

### Example 3: Storage-backed NodeType

```python
# document_indexer.py
# SPDX-License-Identifier: MIT

def handle(inputs, config, storages, state):
    document = inputs["document"]
    
    # Vector search against Chroma
    similar = storages["chroma"].similarity_search(
        document["text"],
        limit=5
    )
    
    # Persist to Postgres
    storages["postgres"].execute(
        "INSERT INTO indexed_documents (content, metadata) VALUES (%s, %s)",
        (document["text"], document.get("metadata", {}))
    )
    
    return {"similar_documents": similar, "indexed_id": "..."}
```

### Example 4: Signal-emitting NodeType

```python
# approval_required_node.py
# SPDX-License-Identifier: Apache-2.0

def handle(inputs, config, storages, state):
    # Send a signal that downstream Wait-for-signal nodes can subscribe to
    storages["__runtime__"].emit_signal(
        channel=f"approval:{inputs['workflow_id']}",
        payload={"requires_approval": True, "context": inputs}
    )
    
    return {"status": "awaiting_approval"}
```

### Example 5: Multi-input NodeType with branching logic

```python
# router_node.py
# SPDX-License-Identifier: Apache-2.0

def handle(inputs, config, storages, state):
    classification = inputs["classification"]
    
    if classification == "urgent":
        return {"output_high_priority": inputs["task"], "output_low_priority": None}
    elif classification == "normal":
        return {"output_high_priority": None, "output_low_priority": inputs["task"]}
    else:
        raise ValueError(f"Unknown classification: {classification}")
```

## Testing your NodeType

The Symdue "Test Node" feature lets you run a NodeType in isolation:

```python
# Simulated runtime call
result = handle(
    inputs={"text": "hello world"},
    config={},
    storages={},  # Pass mock or real storages
    state={}
)
print(result)
```

For container-based testing:

```bash
symdue nodetype test ./my_custom_node.py \
    --inputs '{"text": "hello"}' \
    --config '{}'
```

## Where to register your NodeType

- **Per-workspace** (most common): `POST /api/workspaces/{workspace_id}/node-types`
- **Per-organization** (Enterprise): `POST /api/organizations/{org_id}/node-types` (Enterprise tier feature)
- **Marketplace** (year 2+): publish to the Symdue Marketplace for other users to discover

## Frequently asked

### Can I write a NodeType in TypeScript / Go / Rust?

v1.0 supports Python NodeTypes. TypeScript / Go / Rust NodeTypes are on the v1.x.0 roadmap (the runtime needs language-specific Docker base images and entrypoint adapters).

### Can my NodeType call external APIs?

Yes. Your NodeType runs in a Docker container with full network access. Common patterns: HTTP clients (`requests`, `httpx`), provider SDKs (OpenAI, Anthropic, Stripe, etc.), database clients.

### Can my NodeType use third-party Python packages?

Yes. Declare them in the `requirements` field at registration time:

```json
{
    "requirements": "openai==1.50.0\npydantic==2.5.0"
}
```

The Symdue runtime builds a Docker image with these requirements installed.

### What's the cold-start time?

Roughly 0.5–1 second per Docker container start. v1.x.0 will introduce warm-pool worker mode to amortize this for high-throughput workflows.

### Can I license my NodeType under any license?

Yes. The Apache 2.0 SDK does not impose any constraint on your NodeType code's license. Common choices: Apache 2.0, MIT, BSD, AGPL v3, proprietary, dual-licensed. Your call.

### What happens if Symdue upgrades and my NodeType breaks?

Within v1.x.x runtime versions: it shouldn't break (backwards-compatibility commitment). If it does, that's a Symdue bug — file an issue and we'll fix it.

Across major versions (e.g., v1.x.x → v2.0.0): we'll provide 12 months' notice and a migration guide.

## Reference: Pydantic schemas

For exact field definitions, refer to the Apache 2.0-licensed schema files:

- `server/schemas/node_type.py` — NodeType registration / response / template schemas
- `server/schemas/node.py` — Node instance schema
- `server/schemas/edge.py` — Edge schema (connections between nodes)
- `server/schemas/workflow.py` — Workflow JSON schema
- `server/schemas/storage.py` — StorageConfig schema
- `server/schemas/event.py` — Event runtime schemas
- `server/schemas/signal.py` — Signal/Wait schemas
- `server/schemas/run.py` — Run history schemas
- `server/schemas/llm_config.py` — LLM provider configuration schemas

These are the **public contract**. Importing them in your NodeType code does not introduce AGPL obligations because they are Apache 2.0 licensed.

## Versioning history

| Version | Released | Changes |
|---|---|---|
| 1.0.0 | 2026-05-07 | Initial public API. Python NodeTypes. Six storage backends. Five LLM providers. Documented stable contract. |

## Reporting issues with the API

If you encounter an unstable behavior, undocumented field, or boundary ambiguity, file an issue at [github.com/vinodydev/symdue_oss/issues](https://github.com/vinodydev/symdue_oss/issues). API stability is a commitment we take seriously; reports of stability gaps are high-priority.

## License questions

For questions about how the Apache 2.0 SDK boundary applies to your specific use case, see [docs/FAQ.md](FAQ.md) or contact us at [vinody.dev@gmail.com](mailto:vinody.dev@gmail.com).

For commercial license inquiries (e.g., embedded SaaS use cases that need to escape AGPL on the runtime), see [COMMERCIAL_LICENSE.md](../COMMERCIAL_LICENSE.md).
