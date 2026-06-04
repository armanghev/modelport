"use client";

import { CaretDownIcon } from "@phosphor-icons/react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

export interface MultiFilterOption {
  label: string;
  value: string;
}

function formatTriggerLabel(
  selectedValues: string[],
  options: MultiFilterOption[],
  emptyLabel: string,
): string {
  if (selectedValues.length === 0) {
    return emptyLabel;
  }
  if (selectedValues.length === 1) {
    const match = options.find((option) => option.value === selectedValues[0]);
    return match?.label ?? selectedValues[0];
  }
  return `${selectedValues.length} selected`;
}

export function toggleFilterValue(selectedValues: string[], value: string): string[] {
  return selectedValues.includes(value)
    ? selectedValues.filter((current) => current !== value)
    : [...selectedValues, value];
}

export function MultiFilterSelect({
  id,
  label,
  emptyLabel,
  selectedValues,
  onSelectedValuesChange,
  options,
}: {
  id: string;
  label: string;
  emptyLabel: string;
  selectedValues: string[];
  onSelectedValuesChange: (values: string[]) => void;
  options: MultiFilterOption[];
}) {
  const triggerLabel = formatTriggerLabel(selectedValues, options, emptyLabel);

  return (
    <div className="min-w-0 space-y-1">
      <Popover>
        <PopoverTrigger asChild>
          <Button
            id={id}
            type="button"
            variant="outline"
            aria-label={label}
            className="h-11 w-full justify-between rounded-lg border-border-default px-3 text-xs font-normal text-text-primary"
          >
            <span className="truncate">{triggerLabel}</span>
            <CaretDownIcon size={14} className="shrink-0 text-text-muted" />
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-(--radix-popover-trigger-width) min-w-48 rounded-lg p-2"
        >
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <p className="text-xs font-medium text-text-secondary">{label}</p>
            {selectedValues.length > 0 ? (
              <button
                type="button"
                className="text-xs text-text-muted hover:text-text-primary"
                onClick={() => onSelectedValuesChange([])}
              >
                Clear
              </button>
            ) : null}
          </div>
          <ul className="max-h-56 space-y-0.5 overflow-y-auto">
            {options.map((option) => {
              const checked = selectedValues.includes(option.value);
              return (
                <li key={option.value}>
                  <label
                    className={cn(
                      "flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-xs hover:bg-bg-card-muted",
                      checked && "bg-bg-card-muted",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      className="size-3.5 rounded border-border-default"
                      onChange={() =>
                        onSelectedValuesChange(
                          toggleFilterValue(selectedValues, option.value),
                        )
                      }
                    />
                    <span className="truncate text-text-primary">{option.label}</span>
                  </label>
                </li>
              );
            })}
          </ul>
        </PopoverContent>
      </Popover>
    </div>
  );
}
