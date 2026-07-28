# Quick Start

This quick start brings up the backend proxy and dashboard with the default local configuration from the repository root. Local HTTPS via mkcert is recommended.

## 1. Create local environment variables

```bash
cp .env.example .env
```

On Windows Command Prompt (`cmd.exe`):

```cmd
copy .env.example .env
```

At minimum, set the proxy token and the dashboard token:

```bash
MODELPORT_TOKEN=dev-modelport-token
MODELPORT_DASHBOARD_TOKEN=dev-dashboard-token
```

Then add whichever provider keys you want to use:

```bash
# Required for encrypted DB credentials (see backend/app/security.py)
PROXY_ENCRYPTION_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
OPENROUTER_API_KEY=
```

## 2. Create local TLS certificates

Install [mkcert](https://github.com/FiloSottile/mkcert) and trust its local CA (once per machine):

### macOS

```bash
brew install mkcert
# Optional: needed for Firefox trust store
brew install nss
mkcert -install
```

### Linux

```bash
# Install certutil for browser trust stores (pick your distro)
sudo apt install libnss3-tools
# sudo yum install nss-tools
# sudo pacman -S nss

curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
chmod +x mkcert-v*-linux-amd64
sudo cp mkcert-v*-linux-amd64 /usr/local/bin/mkcert

mkcert -install
```

### Windows

```cmd
:: Chocolatey
choco install mkcert

:: or Scoop
scoop bucket add extras
scoop install mkcert

mkcert -install
```

Generate certificates into `./local/.certs/` from the repository root:

### macOS

```bash
mkdir -p local/.certs
cd local/.certs
mkcert localhost 127.0.0.1 ::1
cd ../..
```

### Linux

```bash
mkdir -p local/.certs
cd local/.certs
mkcert localhost 127.0.0.1 ::1
cd ../..
```

### Windows

```cmd
if not exist local\.certs mkdir local\.certs
cd /d local\.certs
mkcert localhost 127.0.0.1 ::1
cd /d ..\..
```

That creates `localhost+2.pem` and `localhost+2-key.pem`.

**Do not commit certificates.** `local/.certs/` and `*.pem` are gitignored. If you store certs somewhere else, add that path to `.gitignore` before contributing to the main repo.

See [Installation](installation.md) for more detail.

## 3. Start the backend

From the repository root:

### macOS

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
set -a; source .env; set +a
python -m uvicorn app.main:app \
  --app-dir backend \
  --reload \
  --host 127.0.0.1 \
  --port 13243 \
  --ssl-certfile ./local/.certs/localhost+2.pem \
  --ssl-keyfile ./local/.certs/localhost+2-key.pem
```

### Linux

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
set -a; source .env; set +a
python -m uvicorn app.main:app \
  --app-dir backend \
  --reload \
  --host 127.0.0.1 \
  --port 13243 \
  --ssl-certfile ./local/.certs/localhost+2.pem \
  --ssl-keyfile ./local/.certs/localhost+2-key.pem
```

### Windows

```cmd
python -m venv backend\.venv
backend\.venv\Scripts\activate.bat
pip install -r backend\requirements.txt
for /f "usebackq eol=# tokens=1,* delims==" %A in (".env") do set "%A=%B"
python -m uvicorn app.main:app ^
  --app-dir backend ^
  --reload ^
  --host 127.0.0.1 ^
  --port 13243 ^
  --ssl-certfile .\local\.certs\localhost+2.pem ^
  --ssl-keyfile .\local\.certs\localhost+2-key.pem
```

The default proxy URL is:

```text
https://127.0.0.1:13243
```

## 4. Start the dashboard

In a second terminal:

```bash
cd dashboard
pnpm install
```

If the dashboard process does not trust mkcert certificates (common with Node), set:

### macOS

```bash
export NODE_EXTRA_CA_CERTS="$(mkcert -CAROOT)/rootCA.pem"
```

### Linux

```bash
export NODE_EXTRA_CA_CERTS="$(mkcert -CAROOT)/rootCA.pem"
```

### Windows

```cmd
for /f "delims=" %A in ('mkcert -CAROOT') do set "NODE_EXTRA_CA_CERTS=%A\rootCA.pem"
```

Then start the dashboard:

```bash
pnpm dev
```

Open:

```text
http://localhost:3000
```

Point the dashboard at the HTTPS backend and give it the dashboard token (in `dashboard/.env`):

```bash
NEXT_PUBLIC_MODELPORT_BACKEND_URL=https://127.0.0.1:13243
NEXT_PUBLIC_MODELPORT_DASHBOARD_TOKEN=dev-dashboard-token
```

The value must match `MODELPORT_DASHBOARD_TOKEN` in the root `.env`; the backend rejects admin and analytics requests without it.

## 5. Send a test request

OpenAI-style request:

```bash
curl https://127.0.0.1:13243/v1/chat/completions \
  -H "Authorization: Bearer $MODELPORT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-ModelPort-Provider: openai" \
  -d '{
    "model": "gpt-4.1",
    "messages": [
      { "role": "user", "content": "Say hello from ModelPort." }
    ]
  }'
```

Anthropic-style request:

```bash
curl https://127.0.0.1:13243/v1/messages \
  -H "Authorization: Bearer $MODELPORT_TOKEN" \
  -H "Content-Type: application/json" \
  -H "X-ModelPort-Provider: openrouter" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "max_tokens": 128,
    "messages": [
      { "role": "user", "content": "Say hello from ModelPort." }
    ]
  }'
```

## 6. Configure Claude Code

ModelPort includes an interactive CLI that writes Claude Code settings to point at the proxy:

```bash
./bin/modelport-configure
```

Use `https://127.0.0.1:13243` as the proxy base URL when prompted. The tool can write global, project, or local Claude settings and can pull live model lists when the backend is already running.
