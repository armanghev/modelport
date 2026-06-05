'use client';

import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@teispace/next-themes';
import { cva } from 'class-variance-authority';
import { useEffect, useState } from 'react';

import { cn } from '@/lib/utils';

export function DashboardThemeSwitch({
  className,
}: {
  className?: string;
}) {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const value = mounted ? resolvedTheme : null;

  return (
    <button
      type="button"
      className={cn(
        'inline-flex items-center rounded-full border p-1 overflow-hidden *:rounded-full bg-none',
        className,
      )}
      aria-label="Toggle theme"
      data-theme-toggle=""
      onClick={() => setTheme(value === 'light' ? 'dark' : 'light')}
    >
      {value === 'light' ? (
        <Sun
          fill="currentColor"
          className="size-6.5 p-1.5 text-fd-muted-foreground"
        />
      ) : (
        <Moon
          fill="currentColor"
          className="size-6.5 p-1.5 text-fd-muted-foreground"
      />
      )}
    </button>
  );
}
