# Self Hosting

ModelPort is already designed for local or self-hosted deployment.

## Default Runtime Paths

- Backend proxy: `https://127.0.0.1:13243` (local TLS via mkcert)
- Dashboard UI: `https://127.0.0.1:13243/dashboard`
- Database: `./data/modelport.db`
- Config: `./config.yaml`
- Provider credentials: `.env`
- Local TLS certs: `./local/.certs/` (gitignored; generate locally)

## What Self-Hosting Means Today

Self-hosting currently means:

- building the Vite dashboard assets
- running the single FastAPI process that serves both proxy APIs and dashboard
- storing state in local SQLite
- managing provider credentials in environment variables or the local database

## Startup Flow

1. create `.env`
2. run `pnpm --dir dashboard install`
3. run `pnpm --dir dashboard build`
4. create local TLS certificates with mkcert under `./local/.certs/` (see [Installation](../installation.md))
5. start Uvicorn from the repository root with `--ssl-certfile` and `--ssl-keyfile`
6. open `https://127.0.0.1:13243/dashboard` and point clients at the same HTTPS origin

Node is needed only to develop or build frontend assets. The production runtime
is FastAPI plus SQLite. Keep generated assets untracked and rebuild them as part
of each release.

## Certificates

Do not commit mkcert certificates or private keys. The repository gitignores `local/.certs/` and `*.pem`. If you generate certs outside that directory, add the path to `.gitignore` before contributing to the main repo.

OS-specific install and run commands (macOS, Linux, and Windows) are in [Installation](../installation.md) and [Quick Start](../quick-start.md).

## Notes

> **Current maturity:** The backend and dashboard are functional, but the repository does not yet ship a dedicated production deployment package or managed secret backend.
