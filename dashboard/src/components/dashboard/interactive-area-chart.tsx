"use client";

import * as React from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export type DateRangeValue = "90d" | "30d" | "7d";

export interface InteractiveAreaChartPoint {
  date: string;
  primary: number;
  secondary: number;
  cacheRead?: number;
  cacheWrite?: number;
}

export interface InteractiveAreaChartProps {
  data: InteractiveAreaChartPoint[];
  title: string;
  description: string;
  primaryLabel?: string;
  secondaryLabel?: string;
  cacheReadLabel?: string;
  cacheWriteLabel?: string;
  defaultRange?: DateRangeValue;
  className?: string;
}

function filterDataByRange(
  data: InteractiveAreaChartPoint[],
  range: DateRangeValue,
): InteractiveAreaChartPoint[] {
  if (data.length === 0) {
    return data;
  }

  const referenceDate = new Date(data[data.length - 1].date);
  const daysToSubtract = range === "30d" ? 30 : range === "7d" ? 7 : 90;

  const startDate = new Date(referenceDate);
  startDate.setDate(startDate.getDate() - daysToSubtract);

  return data.filter((item) => new Date(item.date) >= startDate);
}

export function InteractiveAreaChart({
  data,
  title,
  description,
  primaryLabel = "Primary",
  secondaryLabel = "Secondary",
  cacheReadLabel = "Cache read",
  cacheWriteLabel = "Cache write",
  defaultRange = "30d",
  className,
}: InteractiveAreaChartProps) {
  const [timeRange, setTimeRange] = React.useState<DateRangeValue>(defaultRange);
  const chartId = React.useId().replace(/:/g, "");
  const rangeOptions: { value: DateRangeValue; label: string }[] = [
    { value: "90d", label: "Last 3 months" },
    { value: "30d", label: "Last 30 days" },
    { value: "7d", label: "Last 7 days" },
  ];

  const filteredData = React.useMemo(
    () => filterDataByRange(data, timeRange),
    [data, timeRange],
  );
  const hasCacheRead = filteredData.some((point) => typeof point.cacheRead === "number");
  const hasCacheWrite = filteredData.some((point) => typeof point.cacheWrite === "number");

  return (
    <article className={cn("card-surface p-0", className)}>
      <header className="flex flex-col gap-3 border-b border-border-subtle px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h2 className="text-xl">{title}</h2>
          <p className="text-sm text-text-secondary">{description}</p>
        </div>

        <Select
          value={timeRange}
          onValueChange={(value) => setTimeRange(value as DateRangeValue)}
        >
          <SelectTrigger className="w-40 rounded-lg bg-bg-card-muted text-sm text-text-primary">
            <SelectValue placeholder="Select range" />
          </SelectTrigger>
          <SelectContent className="rounded-lg p-1">
            {rangeOptions.map((option) => (
              <SelectItem key={option.value} value={option.value} className="rounded-md text-sm">
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </header>

      <div className="h-64 px-4 pt-4 pb-3 sm:px-6 sm:pt-5">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={filteredData}>
            <defs>
              <linearGradient id={`fillPrimary-${chartId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-accent-slate)" stopOpacity={0.45} />
                <stop offset="95%" stopColor="var(--color-accent-slate)" stopOpacity={0.08} />
              </linearGradient>
              <linearGradient id={`fillSecondary-${chartId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-accent-blue)" stopOpacity={0.42} />
                <stop offset="95%" stopColor="var(--color-accent-blue)" stopOpacity={0.1} />
              </linearGradient>
              <linearGradient id={`fillCacheRead-${chartId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-accent-green)" stopOpacity={0.38} />
                <stop offset="95%" stopColor="var(--color-accent-green)" stopOpacity={0.08} />
              </linearGradient>
              <linearGradient id={`fillCacheWrite-${chartId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-accent-amber)" stopOpacity={0.35} />
                <stop offset="95%" stopColor="var(--color-accent-amber)" stopOpacity={0.08} />
              </linearGradient>
            </defs>

            <CartesianGrid strokeDasharray="4 4" stroke="var(--color-chart-grid)" vertical={false} />

            <XAxis
              dataKey="date"
              tickLine={false}
              axisLine={false}
              tickMargin={8}
              minTickGap={32}
              tick={{ fill: "var(--color-text-muted)", fontSize: 12 }}
              tickFormatter={(value) => {
                const date = new Date(value);
                return date.toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                });
              }}
            />

            <Tooltip
              cursor={false}
              contentStyle={{
                borderRadius: 10,
                border: "1px solid var(--color-border-default)",
                backgroundColor: "var(--color-bg-card)",
                color: "var(--color-text-primary)",
              }}
              labelFormatter={(value) => {
                return new Date(value as string).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                });
              }}
            />

            <Area
              dataKey="secondary"
              name={secondaryLabel}
              type="natural"
              fill={`url(#fillSecondary-${chartId})`}
              stroke="var(--color-accent-blue)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3 }}
            />
            <Area
              dataKey="primary"
              name={primaryLabel}
              type="natural"
              fill={`url(#fillPrimary-${chartId})`}
              stroke="var(--color-accent-slate)"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3 }}
            />
            {hasCacheRead ? (
              <Area
                dataKey="cacheRead"
                name={cacheReadLabel}
                type="natural"
                fill={`url(#fillCacheRead-${chartId})`}
                stroke="var(--color-accent-green)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3 }}
              />
            ) : null}
            {hasCacheWrite ? (
              <Area
                dataKey="cacheWrite"
                name={cacheWriteLabel}
                type="natural"
                fill={`url(#fillCacheWrite-${chartId})`}
                stroke="var(--color-accent-amber)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 3 }}
              />
            ) : null}

            <Legend
              verticalAlign="bottom"
              align="right"
              iconType="circle"
              wrapperStyle={{
                color: "var(--color-text-secondary)",
                fontSize: "12px",
                paddingTop: "8px",
              }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </article>
  );
}
