import { DocsLayout } from 'fumadocs-ui/layouts/docs';
import { Outlet } from 'react-router';

import { PageHeader } from '@/components/dashboard/page-header';
import { dashboardTree } from '@/lib/dashboard-tree';
import { baseLayoutOptions } from '@/lib/layout.shared';

export default function DashboardLayout() {
  return (
    <DocsLayout
      tree={dashboardTree}
      {...baseLayoutOptions()}
      sidebar={{
        className: 'bg-fd-card!',
      }}
    >
      <div className="[grid-area:main] min-w-0 px-4 py-6 md:px-9 xl:px-12 bg-fd-background border-l">
        <PageHeader />
        <Outlet />
      </div>
    </DocsLayout>
  );
}
