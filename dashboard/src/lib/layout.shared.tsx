import type { BaseLayoutProps } from 'fumadocs-ui/layouts/shared';

import { DashboardThemeSwitch } from '@/components/dashboard/dashboard-theme-switch';
import { appName, docsRoute, gitConfig } from '@/lib/shared';

export function baseLayoutOptions(): BaseLayoutProps {
  return {
    nav: {
      title: appName,
      url: '/overview',
    },
    githubUrl: `https://github.com/${gitConfig.user}/${gitConfig.repo}`,
    links: [
      {
        type: 'main',
        text: 'Documentation',
        url: docsRoute,
        on: 'nav',
      },
    ],
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
