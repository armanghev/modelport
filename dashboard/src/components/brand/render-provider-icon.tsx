import type { ComponentType, ReactNode, SVGProps } from "react";

import {
  Anthropic,
  Azure,
  Cerebras,
  DeepSeek,
  Fireworks,
  Gemini,
  Groq,
  Meta,
  Mistral,
  Ollama,
  OpenAI,
  OpenRouter,
  Together,
  XAI,
} from "@lobehub/icons";

import { cn } from "@/lib/utils";

type ProviderIconComponent = ComponentType<{ size?: number } & SVGProps<SVGSVGElement>>;

const PROVIDER_ICON_REGISTRY = {
  anthropic: Anthropic,
  azure: Azure.Color,
  cerebras: Cerebras,
  deepseek: DeepSeek,
  fireworks: Fireworks,
  gemini: Gemini.Color,
  google: Gemini.Color,
  groq: Groq,
  meta: Meta.Color,
  mistral: Mistral.Color,
  ollama: Ollama,
  openai: OpenAI,
  openrouter: OpenRouter,
  together: Together,
  xai: XAI,
} satisfies Record<string, ProviderIconComponent>;

type ProviderIconKey = keyof typeof PROVIDER_ICON_REGISTRY;

const PROVIDER_ICON_RESOLVERS: ReadonlyArray<{
  pattern: RegExp;
  key: ProviderIconKey;
}> = [
  { pattern: /anthropic|claude/i, key: "anthropic" },
  { pattern: /azure/i, key: "azure" },
  { pattern: /openrouter/i, key: "openrouter" },
  { pattern: /ollama/i, key: "ollama" },
  { pattern: /together/i, key: "together" },
  { pattern: /deepseek/i, key: "deepseek" },
  { pattern: /cerebras/i, key: "cerebras" },
  { pattern: /fireworks/i, key: "fireworks" },
  { pattern: /\bxai\b|grok/i, key: "xai" },
  { pattern: /gemini|google/i, key: "gemini" },
  { pattern: /groq/i, key: "groq" },
  { pattern: /mistral/i, key: "mistral" },
  { pattern: /meta|llama/i, key: "meta" },
  { pattern: /openai|gpt/i, key: "openai" },
];

function resolveProviderIconKey(provider: string): ProviderIconKey | undefined {
  const normalized = provider.trim().toLowerCase();

  const exactMatch =
    normalized in PROVIDER_ICON_REGISTRY ? (normalized as ProviderIconKey) : undefined;

  return exactMatch ?? PROVIDER_ICON_RESOLVERS.find(({ pattern }) => pattern.test(provider))?.key;
}

function ProviderIconFallback({
  provider,
  className,
}: {
  provider: string;
  className?: string;
}) {
  return (
    <span className={cn("text-xs font-semibold text-text-secondary", className)}>
      {provider.slice(0, 2).toUpperCase()}
    </span>
  );
}

export interface ProviderIconProps {
  provider: string;
  size?: number;
  className?: string;
  fallback?: ReactNode;
}

export function ProviderIcon({
  provider,
  size = 20,
  className,
  fallback,
}: ProviderIconProps) {
  const iconKey = resolveProviderIconKey(provider);
  const Icon = iconKey ? PROVIDER_ICON_REGISTRY[iconKey] : undefined;

  return Icon ? (
    <Icon size={size} className={cn("shrink-0", className)} aria-hidden />
  ) : (
    (fallback ?? <ProviderIconFallback provider={provider} className={className} />)
  );
}

export function renderProviderIcon(provider: string, size = 20) {
  return <ProviderIcon provider={provider} size={size} />;
}
