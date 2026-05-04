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
