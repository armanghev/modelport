import * as React from "react";

import { cn } from "@/lib/utils";

const MARK_VIEWBOX = 128;
const WORDMARK = "ModelPort";

const markStroke = {
  strokeWidth: 7.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

type ModelportIconProps = React.SVGProps<SVGSVGElement> & {
  size?: number;
};

type ModelportWordmarkProps = Omit<React.SVGProps<SVGSVGElement>, "width" | "height"> & {
  height?: number;
  /** Show the background tile on the mark (logo style). */
  withTile?: boolean;
};

function ModelportMarkPaths() {
  return (
    <>
      <path
        d="M 30 96 L 30 34 L 52 66 L 64 34"
        stroke="var(--icon-mark)"
        fill="none"
        {...markStroke}
      />
      <path
        d="M 64 34 L 64 96"
        stroke="var(--icon-mark)"
        fill="none"
        strokeWidth={markStroke.strokeWidth}
        strokeLinecap={markStroke.strokeLinecap}
      />
      <path
        d="M 64 48 C 64 48 102 48 102 68 C 102 88 64 88 64 88"
        stroke="var(--icon-mark)"
        fill="none"
        {...markStroke}
      />
      <line
        x1={36}
        y1={106}
        x2={92}
        y2={106}
        stroke="var(--icon-mark)"
        strokeWidth={5}
        strokeLinecap="round"
      />
      <circle cx={52} cy={74} r={7} fill="var(--icon-mark)" />
    </>
  );
}

function ModelportMarkGroup({ withTile = false }: { withTile?: boolean }) {
  return (
    <>
      {withTile ? (
        <rect x={14} y={14} width={100} height={100} rx={24} fill="var(--icon-tile)" />
      ) : null}
      <ModelportMarkPaths />
    </>
  );
}

function ModelportSvg({
  size = 40,
  className,
  children,
  ...props
}: ModelportIconProps & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox={`0 0 ${MARK_VIEWBOX} ${MARK_VIEWBOX}`}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Modelport"
      className={cn("shrink-0", className)}
      {...props}
    >
      {children}
    </svg>
  );
}

/** Mark only — no background tile. */
export function ModelportIcon(props: ModelportIconProps) {
  return (
    <ModelportSvg {...props}>
      <ModelportMarkPaths />
    </ModelportSvg>
  );
}

/** Mark with background tile. */
export function ModelportLogo(props: ModelportIconProps) {
  return (
    <ModelportSvg {...props}>
      <ModelportMarkGroup withTile />
    </ModelportSvg>
  );
}

/** Full lockup — mark plus ModelPort wordmark. */
export function ModelportWordmark({
  height = 40,
  withTile = false,
  className,
  ...props
}: ModelportWordmarkProps) {
  const gap = 4;
  const fontSize = height * 0.6;
  const letterSpacing = fontSize * -0.02;
  const markWidth = height;
  const textX = markWidth + gap;
  // Sized to fit "ModelPort" at semibold 24px-equivalent without clipping.
  const viewBoxWidth = textX + fontSize * 5.35;

  return (
    <svg
      viewBox={`0 0 ${viewBoxWidth} ${height}`}
      height={height}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="ModelPort"
      className={cn("shrink-0", className)}
      {...props}
    >
      <g transform={`scale(${height / MARK_VIEWBOX})`}>
        <ModelportMarkGroup withTile={withTile} />
      </g>
      <text
        x={textX}
        y={height / 2}
        fill="var(--icon-mark)"
        fontFamily="Inter, ui-sans-serif, system-ui, sans-serif"
        fontSize={fontSize}
        fontWeight={600}
        letterSpacing={letterSpacing}
        dominantBaseline="central"
      >
        {WORDMARK}
      </text>
    </svg>
  );
}

/** @deprecated Use {@link ModelportIcon} instead. */
export const ModelportIconMark = ModelportIcon;
