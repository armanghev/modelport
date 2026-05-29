"use client";

import { useEffect, useMemo } from "react";

import { TrendDownIcon, TrendUpIcon, XIcon } from "@phosphor-icons/react";

import {
  InteractiveAreaChart,
  type InteractiveAreaChartPoint,
} from "@/components/dashboard/interactive-area-chart";

export interface ModelDetailsModalModel {
  displayName: string;
  provider: string;
  modelId: string;
  requestCount: number;
  tokenTotal: number;
  costUsd: number;
  avgLatencyMs: number;
  errorRate: number;
  usageShare: number;
  contextWindow: string;
  usageBars: number[];
}

interface ModelDetailsModalProps {
  model: ModelDetailsModalModel | null;
  onClose: () => void;
  renderProviderIcon: (provider: string) => React.ReactNode;
}

interface ChartPoint {
  x: number;
  y: number;
}

interface ChartPadding {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

function formatInteger(value: number): string {
  return value.toLocaleString("en-US");
}

function formatCost(value: number): string {
  return `$${value.toFixed(2)}`;
}

function buildModalDailyUsageValues(
  usageBars: number[],
  tokenTotal: number,
): number[] {
  const values = usageBars.slice(-7);
  const sum = values.reduce((acc, value) => acc + value, 0);

  if (sum === 0) {
    return values.map(() => 0);
  }

  return values.map((value) => Math.round((tokenTotal * value) / sum));
}

function buildHourlyUsageValues(dailyValues: number[], seed: number): number[] {
  const hourlyValues: number[] = [];
  let state = (seed % 997) + 97;

  dailyValues.forEach((dailyTotal, dayIndex) => {
    const weights: number[] = [];
    let weightSum = 0;

    for (let hour = 0; hour < 24; hour += 1) {
      state = (state * 37 + 19 + dayIndex * 13 + hour * 11) % 1009;
      const noise = (state % 100) / 100;
      const diurnal = 0.55 + 0.45 * Math.sin(((hour - 6) / 24) * Math.PI * 2);
      const weight = Math.max(0.12, diurnal + noise * 0.28);
      weights.push(weight);
      weightSum += weight;
    }

    const dayHourly = weights.map((weight) =>
      Math.max(0, Math.round((dailyTotal * weight) / weightSum)),
    );

    const allocated = dayHourly.reduce((sum, value) => sum + value, 0);
    const remainder = dailyTotal - allocated;
    if (remainder !== 0) {
      const peakIndex = dayHourly.indexOf(Math.max(...dayHourly));
      dayHourly[peakIndex] = Math.max(0, dayHourly[peakIndex] + remainder);
    }

    hourlyValues.push(...dayHourly);
  });

  return hourlyValues;
}

function buildChartPoints(
  values: number[],
  width: number,
  height: number,
  padding: ChartPadding = { top: 10, right: 8, bottom: 20, left: 8 },
): ChartPoint[] {
  if (values.length === 0) {
    return [];
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const range = Math.max(1, maxValue - minValue);
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const stepX = values.length > 1 ? plotWidth / (values.length - 1) : plotWidth;

  return values.map((value, index) => ({
    x: padding.left + index * stepX,
    y: padding.top + ((maxValue - value) / range) * plotHeight,
  }));
}

function pointsToPolyline(points: ChartPoint[]): string {
  return points.map((point) => `${point.x},${point.y}`).join(" ");
}

function pointsToAreaPath(
  points: ChartPoint[],
  height: number,
  baselinePadding = 20,
): string {
  if (points.length === 0) {
    return "";
  }

  const baselineY = height - baselinePadding;
  const first = points[0];
  const last = points[points.length - 1];
  const linePath = points.map((point) => `L ${point.x} ${point.y}`).join(" ");

  return `M ${first.x} ${baselineY} ${linePath} L ${last.x} ${baselineY} Z`;
}

function formatAxisTick(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }

  if (value >= 1_000) {
    return `${Math.round(value / 1_000)}K`;
  }

  return value.toString();
}

export function ModelDetailsModal({
  model,
  onClose,
  renderProviderIcon,
}: ModelDetailsModalProps) {
  useEffect(() => {
    if (!model) {
      return;
    }

    const previousBodyOverflow = document.body.style.overflow;
    const previousHtmlOverflow = document.documentElement.style.overflow;

    document.body.style.overflow = "hidden";
    document.documentElement.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousHtmlOverflow;
    };
  }, [model]);

  useEffect(() => {
    if (!model) {
      return;
    }

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [model, onClose]);

  const modalDailyUsageValues = useMemo(
    () =>
      model
        ? buildModalDailyUsageValues(model.usageBars, model.tokenTotal)
        : [],
    [model],
  );

  const modalHourlyUsageValues = useMemo(
    () =>
      model
        ? buildHourlyUsageValues(
            modalDailyUsageValues,
            model.tokenTotal + model.requestCount,
          )
        : [],
    [modalDailyUsageValues, model],
  );

  const modalHourlyChartData: InteractiveAreaChartPoint[] = useMemo(() => {
    const end = new Date();
    end.setMinutes(0, 0, 0);

    return modalHourlyUsageValues.map((value, index) => {
      const date = new Date(
        end.getTime() -
          (modalHourlyUsageValues.length - 1 - index) * 60 * 60 * 1000,
      );

      return {
        date: date.toISOString(),
        primary: value,
        secondary: value,
      };
    });
  }, [modalHourlyUsageValues]);

  const modalFirstDay = modalDailyUsageValues[0] ?? 0;
  const modalLastDay =
    modalDailyUsageValues[modalDailyUsageValues.length - 1] ?? 0;
  const modalDeltaPercent =
    modalFirstDay > 0
      ? ((modalLastDay - modalFirstDay) / modalFirstDay) * 100
      : 0;
  const modalTrendDirection = modalDeltaPercent >= 0 ? "up" : "down";
  const modalTrendLabel = `${Math.abs(modalDeltaPercent).toFixed(1)}% vs start of week`;

  const modalMiniChartWidth = 520;
  const modalMiniChartHeight = 120;
  const modalMiniChartPadding: ChartPadding = {
    top: 8,
    right: 8,
    bottom: 22,
    left: 34,
  };
  const modalMiniChartPoints = buildChartPoints(
    modalHourlyUsageValues,
    modalMiniChartWidth,
    modalMiniChartHeight,
    modalMiniChartPadding,
  );

  if (!model) {
    return null;
  }

  const modelDetails = [
    {
      key: "totalTokenUsage",
      label: "Token usage (7D)",
      value: formatInteger(model.tokenTotal),
    },
    {
      key: "provider",
      label: "Provider",
      value: model.provider,
    },
    {
      key: "usageShare",
      label: "Usage share",
      value: `${model.usageShare}%`,
    },
    {
      key: "contextWindow",
      label: "Context window",
      value: model.contextWindow,
    },
    {
      key: "avgLatency",
      label: "Average latency",
      value: `${model.avgLatencyMs} ms`,
    },
    {
      key: "errorRate",
      label: "Error rate",
      value: `${model.errorRate}%`,
    },
    {
      key: "estimatedCost",
      label: "Estimated cost",
      value: formatCost(model.costUsd),
    },
    {
      key: "requestCount",
      label: "Requests (7D)",
      value: formatInteger(model.requestCount),
    },
  ];

  return (
    <div
      className="fixed inset-0 z-50 overflow-hidden overscroll-none bg-black/35 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="card-surface mx-auto my-4 max-h-[90vh] w-full max-w-5xl overflow-y-auto p-5 sm:my-6 sm:p-6"
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${model.displayName} details`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border-subtle pb-4">
          <div className="min-w-0 space-y-2">
            <p className="text-sm text-text-secondary">Model details</p>
            <h2 className="truncate text-2xl leading-tight">
              {model.displayName}
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-2 rounded-md border border-border-subtle bg-bg-card-muted px-2.5 py-1 text-xs font-medium text-text-primary">
                <span className="inline-flex h-4 w-4 items-center justify-center text-text-primary">
                  {renderProviderIcon(model.provider)}
                </span>
                {model.provider}
              </span>
            </div>
            <p className="truncate font-mono text-sm text-text-muted">
              {model.modelId}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-border-subtle text-text-muted hover:bg-bg-card-muted hover:text-text-primary"
            aria-label="Close model details"
          >
            <XIcon size={16} />
          </button>
        </div>

        <div className="grid grid-cols-4 gap-3 mt-5">
          {modelDetails.map((detail) => (
            <article key={detail.key} className="card-surface-soft p-4">
              <p className="text-xs text-text-secondary">{detail.label}</p>
              <p className="mt-1 text-sm font-semibold text-text-primary">
                {detail.value}
              </p>
            </article>
          ))}
        </div>

        <article className="card-surface-soft p-4 md:col-span-6 mt-3">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-text-secondary">Usage trend (7D)</p>
            <p className="text-xs text-text-muted">
              Peak {formatInteger(Math.max(...modalDailyUsageValues, 0))}{" "}
              tokens/day
            </p>
          </div>
          <InteractiveAreaChart
            className="mt-2"
            data={modalHourlyChartData}
            dataByRange={{ "7d": modalHourlyChartData }}
            title="Usage trend"
            description="Hourly usage over the last seven days"
            primaryLabel="Token usage"
            defaultRange="7d"
            showHeader={false}
            showRangeSelector={false}
            showLegend={false}
            showSecondary={false}
            surface={false}
            showYAxis
            showVerticalGrid
            chartHeightClassName="h-64"
            yAxisTickFormatter={formatAxisTick}
            tooltipIncludeTime
          />
        </article>
      </div>
    </div>
  );
}
