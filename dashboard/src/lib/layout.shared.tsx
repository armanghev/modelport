import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';

import { DashboardThemeSwitch } from '@/components/dashboard/dashboard-theme-switch';
import { appName, gitConfig } from '@/lib/shared';

export function baseLayoutOptions(): BaseLayoutProps {
  return {
    nav: {
      title: appName,
      url: '/overview',
    },
    githubUrl: `https://github.com/${gitConfig.user}/${gitConfig.repo}`,
    themeSwitch: {
      enabled: true,
      mode: 'light-dark',
    },
    searchToggle: {
      enabled: false,
    },
    slots: {
      themeSwitch: DashboardThemeSwitch,
    },
  };
}
