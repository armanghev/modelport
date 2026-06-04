# ModelPort agent configure

Interactive CLI that points coding agents at your local ModelPort proxy (API URL, bearer token, routing headers, and default models).

Today it configures **Claude Code**. The layout is agent-pluggable so Cursor CLI, Codex, and others can be added later without changing the core flow.

## Quick start

From the ModelPort repository root (with the backend running if you want live model lists):

```bash
python -m venv cli/.venv
source cli/.venv/bin/activate
pip install -e cli/
modelport-configure
```

Or without installing:

```bash
python cli/modelport_agent_config
```

## What it writes

For Claude Code, the tool merges into `settings.json`:

- `env.ANTHROPIC_BASE_URL` — your ModelPort proxy URL
- `env.ANTHROPIC_AUTH_TOKEN` — `MODELPORT_TOKEN` value
- `env.ANTHROPIC_CUSTOM_HEADERS` — includes `X-ModelPort-Provider`
- `env.ANTHROPIC_MODEL` and/or `ANTHROPIC_DEFAULT_*_MODEL` when you pick models
- `env.ENABLE_TOOL_SEARCH=true` — recommended for third-party proxies
- `model` — default model id for the session picker

Scopes:

| Scope | File |
| --- | --- |
| Global (default) | `~/.claude/settings.json` |
| Project | `.claude/settings.json` in the chosen directory |
| Local | `.claude/settings.local.json` in the chosen directory |

Existing keys in those files are preserved; only ModelPort-related `env` entries are updated.

When the backend is running, the model picker only lists **chat-capable** models for coding agents (text output, no embedding/TTS/image-gen/live variants). You can still type a custom model id if needed.

## Non-interactive

```bash
modelport-configure \
  --agent claude-code \
  --scope global \
  --base-url http://127.0.0.1:13243 \
  --token "$MODELPORT_TOKEN" \
  --provider openrouter \
  --model anthropic/claude-sonnet-4 \
  --yes
```

Run `modelport-configure --help` for all flags.

## Adding another agent

1. Add `modelport_agent_config/agents/<agent_id>.py` implementing `AgentAdapter`.
2. Register it in `modelport_agent_config/agents/registry.py`.
3. Map `ModelPortProfile` to that agent’s config files or env vars in `apply()`.
