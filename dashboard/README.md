# ModelPort Dashboard

The dashboard is a React 19 SPA built with Vite. Production assets are emitted
to `backend/app/static/dashboard/` and served by FastAPI at `/dashboard`.
Generated assets are intentionally gitignored.

## Production build

From the repository root:

```bash
pnpm --dir dashboard install
pnpm --dir dashboard build
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 13243
```

Open `http://127.0.0.1:13243/dashboard`. With the recommended local TLS setup,
open `https://127.0.0.1:13243/dashboard` instead.

If the assets have not been built, dashboard routes return a focused `503`;
proxy, health, admin, and analytics routes continue to operate.

## Development

Start FastAPI on port 13243, then run:

```bash
pnpm --dir dashboard install
pnpm --dir dashboard dev
```

Vite serves the SPA under `/dashboard/` and proxies `/admin`, `/analytics`, and
dashboard-auth requests to FastAPI. Browser requests use same-origin cookies and
relative URLs, so no frontend backend-URL or token environment variables are
needed.

## Checks

```bash
pnpm --dir dashboard lint
pnpm --dir dashboard test
pnpm --dir dashboard build
```
