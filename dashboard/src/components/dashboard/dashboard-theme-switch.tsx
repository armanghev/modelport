'use client';

import { MoonIcon, SunIcon } from '@phosphor-icons/react';
import { useTheme } from '@teispace/next-themes';

import { cn } from '@/lib/utils';

export function DashboardThemeSwitch({
  className,
}: {
  className?: string;
}) {
  const { setTheme, resolvedTheme } = useTheme();
  const isLight = resolvedTheme === 'light';

  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center rounded-full border p-1 overflow-hidden *:rounded-full bg-none',
        className,
      )}
      aria-label="Toggle theme"
      data-theme-toggle=""
      onClick={() => setTheme(isLight ? 'dark' : 'light')}
    >
      <SunIcon
        weight="fill"
        className={cn(
          'size-6.5 p-1.5 text-fd-muted-foreground',
          !isLight && 'hidden',
        )}
      />
      <MoonIcon
        weight="fill"
        className={cn(
          'size-6.5 p-1.5 text-fd-muted-foreground',
          isLight && 'hidden',
        )}
      />
    </button>
  );
}
