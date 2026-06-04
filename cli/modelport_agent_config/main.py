from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from modelport_agent_config.agents.base import AgentAdapter, ConfigScope
from modelport_agent_config.agents.registry import get_agent, list_agents
from modelport_agent_config.chat_models import filter_catalog_for_agent
from modelport_agent_config.modelport import (
    ModelPortProfile,
    ModelPortRuntime,
    ProviderModel,
    default_base_url,
    fetch_provider_models,
    find_repo_root,
    load_modelport_runtime,
    normalize_base_url,
    probe_proxy,
    resolve_token,
    resolve_token_with_source,
)
from modelport_agent_config.prompts import (
    print_banner,
    print_step,
    prompt_text,
    prompt_yes_no,
    select_option,
    select_optional,
)


def build_parser() -> argparse.ArgumentParser:
    agents = ", ".join(agent.id for agent in list_agents())
    parser = argparse.ArgumentParser(
        prog="modelport-configure",
        description="Configure CLI coding agents to route through your local ModelPort proxy.",
    )
    parser.add_argument(
        "--agent",
        default="claude-code",
        help=f"Agent to configure ({agents}). More agents can be added under cli/modelport_agent_config/agents/.",
    )
    parser.add_argument(
        "--scope",
        choices=[scope.value for scope in ConfigScope],
        help="Where to write agent settings (global, project, or local).",
    )
    parser.add_argument("--project-dir", type=Path, help="Project directory for project/local scopes.")
    parser.add_argument("--repo-root", type=Path, help="ModelPort repo root (auto-detected by default).")
    parser.add_argument("--base-url", help="ModelPort proxy base URL.")
    parser.add_argument("--token", help="MODELPORT_TOKEN value (overrides env and .env).")
    parser.add_argument("--provider", help="X-ModelPort-Provider value.")
    parser.add_argument("--model", help="Default model id (ANTHROPIC_MODEL and settings model).")
    parser.add_argument("--sonnet-model", help="ANTHROPIC_DEFAULT_SONNET_MODEL override.")
    parser.add_argument("--opus-model", help="ANTHROPIC_DEFAULT_OPUS_MODEL override.")
    parser.add_argument("--haiku-model", help="ANTHROPIC_DEFAULT_HAIKU_MODEL override.")
    parser.add_argument(
        "--disable-tool-search",
        action="store_true",
        help="Do not set ENABLE_TOOL_SEARCH=true (not recommended for proxies).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the settings patch without writing files.")
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt.")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Print patch JSON on stdout.")
    return parser


_HELP_ALIASES = frozenset({"help", "-help", "-h"})


def normalize_argv(argv: list[str] | None) -> list[str]:
    if argv is None:
        argv = sys.argv[1:]
    if len(argv) == 1 and argv[0] in _HELP_ALIASES:
        return ["--help"]
    return argv


def _provider_options(runtime: ModelPortRuntime, catalog: dict[str, list[ProviderModel]]) -> list[tuple[str, str]]:
    ids = list(runtime.provider_ids) or list(catalog.keys())
    options: list[tuple[str, str]] = []
    for provider_id in ids:
        models = catalog.get(provider_id, [])
        suffix = f" — {len(models)} chat models" if models else ""
        options.append((provider_id, f"{provider_id}{suffix}"))
    if not options:
        options.append(("openrouter", "openrouter"))
    return options


def _model_options(
    provider_id: str,
    catalog: dict[str, list[ProviderModel]],
    *,
    limit: int = 60,
) -> list[tuple[str, str]]:
    models = catalog.get(provider_id, [])
    options: list[tuple[str, str]] = []
    for model in models[:limit]:
        label = model.display_name or model.id
        options.append((model.id, label))
    return options


def _suggested_models(provider_id: str, catalog: dict[str, list[ProviderModel]]) -> list[str]:
    options = [model_id for model_id, _ in _model_options(provider_id, catalog)]
    if options:
        return options
    if provider_id == "openrouter":
        return [
            "anthropic/claude-sonnet-4",
            "anthropic/claude-opus-4",
            "openai/gpt-4o-mini",
        ]
    if provider_id == "anthropic":
        return ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]
    if provider_id == "ollama":
        return ["qwen2.5-coder:latest"]
    return []


def collect_profile_interactive(
    runtime: ModelPortRuntime,
    adapter: AgentAdapter,
    *,
    scope: ConfigScope | None,
    project_dir: Path,
) -> tuple[ModelPortProfile, ConfigScope]:
    print_banner(
        "ModelPort agent configure",
        "Route Claude Code (and future agents) through your local ModelPort proxy.",
    )

    if not adapter.detect_installed():
        print("Note: Claude Code was not detected in PATH or ~/.claude — settings will still be written.")

    scope_options = [
        (ConfigScope.GLOBAL.value, "User-wide (~/.claude/settings.json)"),
        (ConfigScope.PROJECT.value, "Project (.claude/settings.json)"),
        (ConfigScope.LOCAL.value, "Project-local (.claude/settings.local.json)"),
    ]
    scope_value = scope.value if scope else select_option("Settings scope", scope_options)
    resolved_scope = ConfigScope(scope_value)

    if resolved_scope is not ConfigScope.GLOBAL:
        project_dir = Path(
            prompt_text("Project directory", str(project_dir)),
        ).expanduser().resolve()

    default_url = default_base_url(runtime)
    base_url = normalize_base_url(prompt_text("ModelPort base URL", default_url))

    token_resolution = resolve_token_with_source(runtime)
    if token_resolution:
        print(f"  Token: using value from {token_resolution.source}.")
        token = token_resolution.token
    else:
        token = prompt_text(f"{runtime.token_env}", secret=True)
    if not token:
        raise SystemExit(f"{runtime.token_env} is required.")

    ok, message = probe_proxy(base_url, token)
    print(f"  Proxy check: {message}")
    if not ok:
        if not prompt_yes_no("Continue anyway?"):
            raise SystemExit(1)

    raw_catalog = fetch_provider_models(base_url)
    catalog, excluded = filter_catalog_for_agent(raw_catalog, agent_id=adapter.id)
    if raw_catalog:
        total = sum(len(models) for models in raw_catalog.values())
        chat_total = sum(len(models) for models in catalog.values())
        print(
            f"  Loaded {total} models from the backend; "
            f"showing {chat_total} chat-capable for {adapter.display_name}."
        )
        if excluded:
            print(
                f"  Hid {excluded} embedding, audio, image-gen, live, and other non-chat models."
            )
    else:
        print("  Backend model catalog unavailable — you can type model ids manually.")

    provider_id = select_option(
        "Default provider (sent as X-ModelPort-Provider)",
        _provider_options(runtime, catalog),
        allow_custom=True,
        custom_label="Type another provider id",
    )

    model_choices = _model_options(provider_id, catalog)
    if not model_choices:
        for suggestion in _suggested_models(provider_id, catalog):
            model_choices.append((suggestion, suggestion))

    model = select_optional(
        "Default model",
        model_choices,
    )

    configure_tiers = prompt_yes_no("Override Sonnet / Opus / Haiku default models?")
    sonnet_model = opus_model = haiku_model = None
    if configure_tiers:
        tier_options = model_choices or [(m, m) for m in _suggested_models(provider_id, catalog)]
        sonnet_model = select_optional("Sonnet tier (ANTHROPIC_DEFAULT_SONNET_MODEL)", tier_options)
        opus_model = select_optional("Opus tier (ANTHROPIC_DEFAULT_OPUS_MODEL)", tier_options)
        haiku_model = select_optional("Haiku tier (ANTHROPIC_DEFAULT_HAIKU_MODEL)", tier_options)

    profile = ModelPortProfile(
        base_url=base_url,
        token=token,
        provider_id=provider_id.strip().lower(),
        model=model,
        sonnet_model=sonnet_model,
        opus_model=opus_model,
        haiku_model=haiku_model,
        enable_tool_search=True,
    )
    return profile, resolved_scope


def collect_profile_from_args(
    args: argparse.Namespace,
    runtime: ModelPortRuntime,
) -> tuple[ModelPortProfile, ConfigScope]:
    missing: list[str] = []
    if not args.base_url:
        missing.append("--base-url")
    if not args.token and not resolve_token(runtime):
        missing.append("--token")
    if not args.provider:
        missing.append("--provider")
    if missing:
        raise SystemExit(f"Non-interactive mode requires: {', '.join(missing)}")

    base_url = normalize_base_url(args.base_url or default_base_url(runtime))
    token = resolve_token(runtime, args.token)
    if not token:
        raise SystemExit(f"{runtime.token_env} is required.")

    scope = ConfigScope(args.scope or ConfigScope.GLOBAL.value)
    profile = ModelPortProfile(
        base_url=base_url,
        token=token,
        provider_id=str(args.provider).strip().lower(),
        model=args.model,
        sonnet_model=args.sonnet_model,
        opus_model=args.opus_model,
        haiku_model=args.haiku_model,
        enable_tool_search=not args.disable_tool_search,
    )
    return profile, scope


def preview_patch(adapter: AgentAdapter, profile: ModelPortProfile) -> dict:
    return adapter.build_settings_patch(profile)


def _run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(normalize_argv(argv))

    repo_root = args.repo_root or find_repo_root()
    runtime = load_modelport_runtime(repo_root)
    project_dir = (args.project_dir or repo_root).expanduser().resolve()

    try:
        adapter = get_agent(args.agent)
    except KeyError as exc:
        parser.error(str(exc))

    interactive = sys.stdin.isatty() and not args.json_output and not (
        args.base_url and args.token and args.provider
    )

    if interactive and not args.scope:
        profile, scope = collect_profile_interactive(runtime, adapter, scope=None, project_dir=project_dir)
    else:
        profile, scope = collect_profile_from_args(args, runtime)
        if args.scope:
            scope = ConfigScope(args.scope)

    patch = preview_patch(adapter, profile)
    settings_path = adapter.config_path(scope, project_dir)

    if args.json_output:
        print(
            json.dumps(
                {
                    "agent": adapter.id,
                    "scope": scope.value,
                    "settings_path": str(settings_path),
                    "patch": patch,
                },
                indent=2,
            )
        )
        return 0

    print_step("Summary")
    print(f"  Agent:     {adapter.display_name}")
    print(f"  Scope:     {scope.value}")
    print(f"  File:      {settings_path}")
    print(f"  Base URL:  {profile.base_url}")
    print(f"  Provider:  {profile.provider_id}")
    print(f"  Model:     {profile.model or '(agent default)'}")
    for label, model_id in profile.anthropic_tier_overrides():
        print(f"  {label + ':':<11}{model_id}")
    print(f"  Headers:\n    {profile.format_custom_headers().replace(chr(10), chr(10) + '    ')}")

    if args.dry_run:
        print("\nDry run — settings patch:")
        print(json.dumps(patch, indent=2))
        return 0

    if not args.yes and sys.stdin.isatty():
        if not prompt_yes_no("Write these settings?"):
            print("Cancelled.")
            return 0

    result = adapter.apply(profile, scope, project_dir)
    adapter.print_post_apply_hints(profile, result)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(argv)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return 130
    except EOFError:
        print("\nCancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
