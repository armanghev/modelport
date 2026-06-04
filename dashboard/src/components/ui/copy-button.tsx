"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { CheckIcon, CopyIcon } from "@phosphor-icons/react";

import { cn } from "@/lib/utils";

interface CopyButtonProps {
  value: string;
  label?: string;
  copiedLabel?: string;
  iconSize?: number;
  className?: string;
  "aria-label"?: string;
  disabled?: boolean;
}

export function CopyButton({
  value,
  label,
  copiedLabel = "Copied",
  iconSize = 12,
  className,
  "aria-label": ariaLabel,
  disabled = false,
}: CopyButtonProps) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const handleCopy = useCallback(async () => {
    if (disabled || !value) {
      return;
    }

    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = window.setTimeout(() => {
        setCopied(false);
        timeoutRef.current = null;
      }, 1500);
    } catch {
      // Clipboard access can fail silently in unsupported contexts.
    }
  }, [disabled, value]);

  const Icon = copied ? CheckIcon : CopyIcon;

  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={copied ? copiedLabel : ariaLabel ?? label ?? "Copy"}
      className={cn(
        "inline-flex items-center gap-1 transition-colors",
        copied ? "text-accent-green" : "text-text-muted hover:text-text-primary",
        className,
      )}
      onClick={() => void handleCopy()}
    >
      <Icon size={iconSize} weight={copied ? "bold" : "regular"} />
      {label ? <span>{copied ? copiedLabel : label}</span> : null}
    </button>
  );
}
