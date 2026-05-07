# Contributing

Thanks for considering a contribution. This repo is in early public release — expect rough edges and a small but responsive maintainer team.

## Quick links

- **Bugs / feature requests:** open a GitHub issue. Include reproduction steps, your OS, and the relevant parts of `docker compose logs` if you can.
- **Security disclosures:** see [SECURITY.md](SECURITY.md). Please do not file public issues for security problems.
- **Code of conduct:** see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Local dev setup

The fastest path is the Docker Compose stack:

```bash
cp server/.env.example server/.env
cd setup
docker compose up
```

That brings up Postgres, Redis, Temporal, MinIO, the backend, the Temporal worker, and the frontend. The frontend is on `http://localhost:3000`, the API on `http://localhost:8000`, and the Temporal UI on `http://localhost:8089`.

For a non-Docker workflow, look at:

- [`setup/setup-db.sh`](setup/setup-db.sh) — bootstrap a local Postgres
- [`setup/setup-mac.sh`](setup/setup-mac.sh) — macOS-specific dev setup
- [`server/setup/setup.sh`](server/setup/setup.sh) — backend dev install
- `server/requirements.txt` and `server/requirements-dev.txt` for Python deps

## Running tests

```bash
cd server
pytest
```

Frontend tests:

```bash
cd client
npm install
npm test
```

## Pull requests

1. Fork, branch, push, open a PR against `main`.
2. Keep PRs focused — one logical change per PR.
3. New behavior should land with at least one test.
4. The PR description should explain *why*; the diff explains *what*.

We'll iterate with you on review. If something isn't documented well enough to figure out from code, that's a bug — say so.

## Licensing your contribution

Symdue is **dual-licensed**: the runtime is AGPL v3, the plugin SDK and demos are Apache 2.0. See [LICENSE](LICENSE) for the full structure.

Where your contribution lands determines what's required:

### Runtime contributions (AGPL v3 — most code lives here)

If your contribution is to the runtime — `server/runtime/`, `server/services/`, `server/api/`, `server/database/`, `server/middleware/`, `client/`, `setup/`, etc. — you'll need to **sign the [Contributor License Agreement (CLA)](CLA.md)**.

The CLA gives Symdue the right to relicense your contribution under non-AGPL commercial terms when selling commercial licenses to specific customers (per [COMMERCIAL_LICENSE.md](COMMERCIAL_LICENSE.md)). You retain copyright.

**How to sign**: open your first PR. The CLA Assistant bot will detect that you haven't signed and post a comment with a "sign the CLA" link. Click, sign in with GitHub OAuth, done. You only need to sign once per GitHub account.

This is the standard pattern for dual-licensed OSS projects: Grafana, Sentry, HashiCorp, Cal.com, PostHog all use the same model.

### Apache 2.0 SDK / spec / demo contributions (no CLA required)

Contributions to `server/schemas/` (the public API spec), `demos/`, or future Apache 2.0 directories don't require the CLA. Instead, sign-off your commits with the standard [Developer Certificate of Origin (DCO)](https://developercertificate.org/):

```
Signed-off-by: Your Name <your.email@example.com>
```

Use `git commit -s` to add this automatically.

### Why two contribution paths?

The Apache 2.0 SDK is the public boundary that custom NodeType authors build against. We want maximum contribution velocity here with minimum friction (no CLA) so the ecosystem grows.

The AGPL runtime is the core differentiated work. We need the right to relicense it commercially to sustain the company, which requires the CLA on contributions.

This split mirrors what MySQL does (GPL core + LGPL connectors, with stricter contribution terms on the GPL portion) and what most successful dual-licensed OSS projects do.

### What if your employer restricts CLAs?

If you can't sign the CLA personally because of employer policy, we can:

- Have your employer sign on behalf of contributors (corporate CCLA, see CLA Assistant for the workflow)
- Route your contribution to the Apache 2.0 SDK or demos directories where DCO is sufficient
- Discuss alternative arrangements

Email [vinody.dev@gmail.com](mailto:vinody.dev@gmail.com) before contributing if you're unsure.
