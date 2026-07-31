# Installation

ModelPort currently has three installable parts:

- the FastAPI backend
- the Vite-built dashboard assets served by FastAPI
- the optional `modelport-configure` CLI

## Backend

### macOS

```bash
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### Linux

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### Windows

```cmd
python -m venv backend\.venv
backend\.venv\Scripts\activate.bat
pip install -r backend\requirements.txt
```

### Local HTTPS (recommended)

Local TLS uses [mkcert](https://github.com/FiloSottile/mkcert) so browsers and clients trust `https://127.0.0.1` without disabling certificate verification.

#### 1. Install mkcert and trust the local CA

Do this once per machine.

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

# Pre-built binary (amd64). For arm64 use for=linux/arm64
curl -JLO "https://dl.filippo.io/mkcert/latest?for=linux/amd64"
chmod +x mkcert-v*-linux-amd64
sudo cp mkcert-v*-linux-amd64 /usr/local/bin/mkcert

# Arch Linux alternative:
# sudo pacman -Syu mkcert

mkcert -install
```

### Windows

```cmd
:: Chocolatey
choco install mkcert

:: or Scoop
scoop bucket add extras
scoop install mkcert

:: If you hit permission errors, run this step in an elevated Command Prompt
mkcert -install
```

#### 2. Generate certificates

From the repository root, create certs under `./local/.certs/`:

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

That creates `localhost+2.pem` (certificate) and `localhost+2-key.pem` (private key). Filenames follow mkcert’s `name+N` pattern when you pass multiple hostnames/IPs.

#### 3. Do not commit certificates

`local/.certs/` and `*.pem` are listed in the repository `.gitignore`. If you place certs elsewhere, add that path to `.gitignore` before contributing to the main repo.

#### 4. Start the backend with TLS

Run from the repository root so `config.yaml`, `.env`, and `pricing_catalog.yaml` resolve as expected:

### macOS

```bash
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
for /f "usebackq eol=# tokens=1,* delims==" %A in (".env") do set "%A=%B"
python -m uvicorn app.main:app ^
  --app-dir backend ^
  --reload ^
  --host 127.0.0.1 ^
  --port 13243 ^
  --ssl-certfile .\local\.certs\localhost+2.pem ^
  --ssl-keyfile .\local\.certs\localhost+2-key.pem
```

Uvicorn should report `https://127.0.0.1:13243`. Plain HTTP still works if you omit the `--ssl-*` flags.

## Dashboard

Install frontend dependencies and produce the static build from the repository
root:

```bash
pnpm --dir dashboard install
pnpm --dir dashboard build
```

Then start Uvicorn as shown above and open:

```text
https://127.0.0.1:13243/dashboard
```

The compiled files live in the gitignored
`backend/app/static/dashboard/` directory. They are never generated during
backend startup. If they are missing, dashboard routes return `503` while the
proxy and API routes remain available.

For frontend development, start FastAPI and run:

```bash
pnpm --dir dashboard dev
```

Vite serves `/dashboard/` and proxies dashboard API paths to FastAPI. No
frontend URL or token environment variables are required for the documented TLS
setup. If the backend is running over plain HTTP, use
`MODELPORT_BACKEND_DEV_URL=http://127.0.0.1:13243 pnpm --dir dashboard dev`.

## Docs

Documentation lives as plain markdown under `docs/`. Start from [README.md](README.md).

## CLI

You can run the CLI from the repository without installing it:

```bash
python cli/modelport_agent_config
```

Or install it in a virtual environment:

### macOS

```bash
python -m venv cli/.venv
source cli/.venv/bin/activate
pip install -e cli/
modelport-configure
```

### Linux

```bash
python3 -m venv cli/.venv
source cli/.venv/bin/activate
pip install -e cli/
modelport-configure
```

### Windows

```cmd
python -m venv cli\.venv
cli\.venv\Scripts\activate.bat
pip install -e cli\
modelport-configure
```

## Required Configuration

The backend reads:

- `config.yaml` for seeded providers and database location
- `.env` for proxy/dashboard authentication and provider API keys

At minimum:

```bash
MODELPORT_TOKEN=dev-modelport-token
MODELPORT_DASHBOARD_TOKEN=dev-dashboard-token
MODELPORT_DASHBOARD_AUTH_ENABLED=true
```

Provider keys are optional until you route traffic to those providers. Ollama is the exception because its default local setup does not require an API key.
