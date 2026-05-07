# Scheduling workflows in Symdue OSS

The OSS substrate doesn't include a built-in scheduler. The `Event` feature that would have provided one is **disabled by default** for security reasons (see [SECURITY.md § 2](../SECURITY.md)).

This page covers the three patterns most users rely on for scheduled, queue-driven, or webhook-driven workflows in OSS Symdue.

---

## Pattern 1 — External cron + curl

The simplest pattern. Run cron (Linux), launchd (macOS), Task Scheduler (Windows), or a Kubernetes CronJob; have it `curl POST /api/runs` against your Symdue instance.

### Linux/macOS crontab example

Find your workflow ID first (UI → workspace → "..." → Copy ID; or `GET /api/workspaces`).

```cron
# Every 5 minutes, run the "daily_sync" workflow with empty input
*/5 * * * * curl -sSf -X POST http://localhost:8000/api/runs \
                  -H 'Content-Type: application/json' \
                  -d '{"workflow_id": "<workflow-uuid>", "input": {}}'
```

> When [API authentication](../SECURITY.md) lands in a future release, add `-H "X-API-Key: $FLOWGRAPH_API_KEY"`.

### Kubernetes CronJob example

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: symdue-daily-sync
  namespace: symdue
spec:
  schedule: "0 9 * * *"   # 9am daily
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: trigger
            image: curlimages/curl:8
            command: ["sh", "-c"]
            args:
              - |
                curl -sSf -X POST http://symdue-backend:8000/api/runs \
                  -H 'Content-Type: application/json' \
                  -d '{"workflow_id":"<workflow-uuid>","input":{}}'
```

### When to use this pattern

- One-off "run X every N minutes" use cases
- You already have cron / k8s in your stack
- You want triggers stored outside Symdue (DR / portability)

---

## Pattern 2 — Wait + Signal channel

The substrate's existing **Wait node** + **signal channel** primitive lets a workflow block on a named channel; an external publisher wakes it.

### Workflow shape

1. In the canvas, drop a **Wait node** at the start of the workflow.
2. Configure: `mode: signal`, `channel: tick` (any name; same name on publish side).
3. Connect downstream nodes — they only run after Wait wakes.
4. Save the workflow.

When you start a run, it pauses at the Wait node and stays there until something publishes to the `tick` channel.

### Publishing a signal — via the API

```bash
curl -sSf -X POST http://localhost:8000/api/signals/channels/tick/emit \
     -H 'Content-Type: application/json' \
     -d '{"data": {"trigger": "manual", "ts": "2026-05-01T12:00:00Z"}}'
```

The `data` payload arrives as the Wait node's output and flows downstream.

### Publishing a signal — via Redis directly

The substrate uses Redis pubsub under the hood. You can publish from any language with a Redis client:

```python
import redis, json, datetime
r = redis.Redis(host='localhost', port=6379)
r.publish("signal:tick", json.dumps({"now": datetime.datetime.utcnow().isoformat()}))
```

### When to use this pattern

- One workflow definition that responds to many trigger types
- The trigger source is event-driven (not time-driven)
- Multiple publishers fan-in to one workflow
- You want the workflow to be "always running, occasionally working" rather than spawned-per-trigger

---

## Pattern 3 — Webhook → external receiver → workflow

For webhook-driven workflows (GitHub push, Stripe event, calendar bookings, etc.), point the webhook at a small HTTP receiver that:

1. Validates the signature
2. Translates the payload into a `POST /api/runs` body
3. Forwards to Symdue

### Caddy example

```caddyfile
api.example.com {
  route /github-webhook {
    @sig header X-Hub-Signature-256 *
    handle @sig {
      reverse_proxy http://symdue-backend:8000 {
        rewrite "POST /api/runs"
        header_up Content-Type application/json
        # Use Caddy's request_body / header transforms to reshape
      }
    }
    respond 401
  }
}
```

For payload transforms more complex than Caddy can express, run the receiver as a small FastAPI sidecar, an AWS Lambda, or a Cloudflare Worker.

### When to use this pattern

- The trigger comes from an external system you don't control
- You need signature validation
- You need payload transformation before Symdue sees it

---

## Patterns we deliberately do not recommend

- **Manually flipping `EVENT_SCRIPTS_ENABLED=true` in production** — this re-exposes finding C1 unless the substrate is behind an authenticating proxy. If your deployment is single-tenant and behind such a proxy, it's a defensible choice; if not, prefer one of the three patterns above. See [SECURITY.md § 2](../SECURITY.md) for the trust model.

---

## Looking ahead — Cloud / managed tier

The closed managed (BYOC) tier ships the Event-script feature with proper container isolation, so the patterns above become optional rather than required. If you'd prefer not to operate cron / signal publishers / webhook receivers yourself, the managed tier handles them.
