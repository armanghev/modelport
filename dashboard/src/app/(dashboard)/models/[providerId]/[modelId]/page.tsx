"use client";

import { useEffect, useMemo, useState } from "react";

import { useParams } from "next/navigation";

import { ModelDetailView } from "@/components/dashboard/models/model-detail-view";
import { fetchProviderModels } from "@/lib/admin-api";
import { flattenProviderModels } from "@/lib/models-directory";

export default function ModelDetailPage() {
  const params = useParams<{ providerId: string; modelId: string }>();
  const providerId = decodeURIComponent(params.providerId ?? "");
  const modelId = decodeURIComponent(params.modelId ?? "");

  const [payload, setPayload] = useState<Awaited<ReturnType<typeof fetchProviderModels>> | null>(
    null,
  );
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void (async () => {
      try {
        const nextPayload = await fetchProviderModels();
        if (!active) {
          return;
        }
        setPayload(nextPayload);
        setErrorMessage(null);
      } catch (error) {
        if (!active) {
          return;
        }
        setErrorMessage(
          error instanceof Error ? error.message : "Failed to load model details.",
        );
      } finally {
        if (active) {
          setIsLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  const selectedRow = useMemo(() => {
    const rows = flattenProviderModels(payload?.providers ?? []);
    return (
      rows.find((row) => row.providerId === providerId && row.model.id === modelId) ?? null
    );
  }, [modelId, payload, providerId]);

  if (isLoading) {
    return <div className="text-sm text-text-secondary">Loading model details...</div>;
  }

  if (errorMessage) {
    return (
      <div className="rounded-xl border border-accent-red/20 bg-accent-red-bg px-4 py-3 text-sm text-accent-red">
        {errorMessage}
      </div>
    );
  }

  if (!selectedRow) {
    return (
      <div className="card-surface px-5 py-10 text-center text-sm text-text-muted">
        Model not found in the current healthy provider catalogs.
      </div>
    );
  }

  return <ModelDetailView row={selectedRow} />;
}
