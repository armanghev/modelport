import type { ComponentType, ReactNode, SVGProps } from "react";

import Anthropic from "@lobehub/icons/es/Anthropic/components/Mono";
import Azure from "@lobehub/icons/es/Azure/components/Color";
import Cerebras from "@lobehub/icons/es/Cerebras/components/Mono";
import DeepSeek from "@lobehub/icons/es/DeepSeek/components/Mono";
import Fireworks from "@lobehub/icons/es/Fireworks/components/Mono";
import Gemini from "@lobehub/icons/es/Gemini/components/Color";
import Groq from "@lobehub/icons/es/Groq/components/Mono";
import Meta from "@lobehub/icons/es/Meta/components/Color";
import Mistral from "@lobehub/icons/es/Mistral/components/Color";
import Ollama from "@lobehub/icons/es/Ollama/components/Mono";
import OpenAI from "@lobehub/icons/es/OpenAI/components/Mono";
import OpenRouter from "@lobehub/icons/es/OpenRouter/components/Mono";
import Together from "@lobehub/icons/es/Together/components/Mono";
import XAI from "@lobehub/icons/es/XAI/components/Mono";

import { cn } from "@/lib/utils";

type ProviderIconComponent = ComponentType<{ size?: number } & SVGProps<SVGSVGElement>>;

const PROVIDER_ICON_REGISTRY = {
  anthropic: Anthropic,
  azure: Azure,
  cerebras: Cerebras,
  deepseek: DeepSeek,
  fireworks: Fireworks,
  gemini: Gemini,
  google: Gemini,
  groq: Groq,
  meta: Meta,
  mistral: Mistral,
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
