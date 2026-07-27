# ModelPort agent configure

Interactive CLI that points coding agents at your local ModelPort proxy (API URL, bearer token, and default models).

Today it configures **Claude Code** only (`--agent claude-code`).

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
- `env.ANTHROPIC_MODEL` and/or `ANTHROPIC_DEFAULT_*_MODEL` when you pick models
- `env.ENABLE_TOOL_SEARCH=true` — recommended for third-party proxies
- `model` — default model id for the session picker

ModelPort infers provider routing from each model id (for example `gemini/models/gemini-2.5-flash`, `openai/gpt-4.1`, or OpenRouter vendor ids like `anthropic/claude-sonnet-4`). No `X-ModelPort-Provider` custom header is written.

Scopes:

| Scope | File |
| --- | --- |
| Global (default) | `~/.claude/settings.json` |
| Project | `.claude/settings.json` in the chosen directory |
| Local | `.claude/settings.local.json` in the chosen directory |

Existing keys in those files are preserved; only ModelPort-related `env` entries are updated. Old `ANTHROPIC_CUSTOM_HEADERS` entries are removed on apply.

## Model picker

When the backend is running, the interactive flow shows **provider tabs** (openrouter, gemini, openai, etc.). Use `←`/`→` or `Tab` to switch providers; the model list filters to that provider. Type to search within the active tab. You can assign different providers per tier—for example a Gemini model for Sonnet and an OpenAI model for Opus.

The picker only lists **chat-capable** models for coding agents (text output, no embedding/TTS/image-gen/live variants). You can still type a custom model id.

## Non-interactive

```bash
modelport-configure \
  --agent claude-code \
  --scope global \
  --base-url http://127.0.0.1:13243 \
  --token "$MODELPORT_TOKEN" \
  --model anthropic/claude-sonnet-4 \
  --sonnet-model models/gemini-2.5-flash \
  --yes
```

Run `modelport-configure --help` for all flags.

## Adding another agent

There is no adapter registry today. `main.resolve_adapter()` accepts `claude-code` and returns `ClaudeCodeAdapter` from `agents/claude_code.py`; anything else errors.

To add a second agent:

1. Add `modelport_agent_config/agents/<agent_id>.py` with the same shape as `ClaudeCodeAdapter` (config path, settings patch, apply).
2. Teach `resolve_adapter()` (or reintroduce a small registry) to return it for that `--agent` id.
3. Map `ModelPortProfile` to that agent’s config files or env vars in `apply()`.
