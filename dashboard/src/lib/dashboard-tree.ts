import type * as PageTree from 'fumadocs-core/page-tree';

export const dashboardTree: PageTree.Root = {
  name: 'Dashboard',
  children: [
    { type: 'page', name: 'Overview', url: '/overview' },
    { type: 'page', name: 'Requests', url: '/requests' },
    { type: 'page', name: 'Models', url: '/models' },
    { type: 'page', name: 'Providers', url: '/providers' },
    { type: 'page', name: 'Costs', url: '/costs' },
    { type: 'page', name: 'Settings', url: '/settings' },
  ],
};
