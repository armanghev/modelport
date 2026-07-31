import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router";

import DashboardLayout from "@/app/(dashboard)/layout";

const CostsPage = lazy(() => import("@/app/(dashboard)/costs/page"));
const ModelDetailPage = lazy(
  () => import("@/app/(dashboard)/models/[providerId]/[modelId]/page"),
);
const ModelsPage = lazy(() => import("@/app/(dashboard)/models/page"));
const OverviewPage = lazy(() => import("@/app/(dashboard)/overview/page"));
const ProvidersPage = lazy(() => import("@/app/(dashboard)/providers/page"));
const RequestsPage = lazy(() => import("@/app/(dashboard)/requests/page"));
const SettingsPage = lazy(() => import("@/app/(dashboard)/settings/page"));

export function DashboardRoutes() {
  return (
    <Suspense
      fallback={
        <div className="p-6 text-sm text-text-secondary">
          Loading dashboard…
        </div>
      }
    >
      <Routes>
        <Route element={<DashboardLayout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<OverviewPage />} />
          <Route path="requests" element={<RequestsPage />} />
          <Route path="models" element={<ModelsPage />} />
          <Route
            path="models/:providerId/:modelId"
            element={<ModelDetailPage />}
          />
          <Route path="providers" element={<ProvidersPage />} />
          <Route path="costs" element={<CostsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
