# ModelPort Dashboard Design Spec

## Product Direction

The dashboard should feel like a calm, local-first developer tool: useful, quiet, and trustworthy. It should not feel like a generic AI SaaS template. The interface should prioritize clarity over visual noise, with only the metrics a developer would actually check while routing model traffic.

The visual tone is neutral, slightly warm, and technical without looking cold. Think: a clean internal analytics tool, not a flashy marketing dashboard.

## Core Design Principles

1. **Useful first**
   - Every card should answer a real question:
     - How many tokens did I use?
     - What did it cost?
     - Which model/provider is being used most?
     - Is the proxy healthy?
     - Which requests just happened?

2. **Low density**
   - Avoid cramming the screen with tiny charts and vanity metrics.
   - Prefer fewer sections with more breathing room.
   - Tables should show only the most useful columns by default.

3. **Neutral and durable**
   - Use off-white, stone, gray, slate, and charcoal.
   - Avoid neon gradients, heavy glows, and “AI-looking” visual effects.
   - Color should mainly communicate state, not decoration.

4. **Developer-friendly**
   - The dashboard should feel like something a developer can keep open all day.
   - Use clear labels, readable numbers, and fast scanning patterns.

---

## Brand Name

**Local AI Proxy**

Optional future product names:
- ProxyDesk
- ModelGate
- RouteKit
- TokenDesk
- LocalBridge

For now, **Local AI Proxy** is clear and self-explanatory.

---

## Logo Concept

The logo is a geometric routing mark. It combines:
- a hexagon/cube-like outer shell for infrastructure
- internal crossing paths for routing and translation
- a center node for the proxy layer

It should feel technical, local, and minimal. It should not look like a chatbot logo.

### Logo Usage

Use the icon alone in small spaces:

```txt
[icon]
```

Use the icon with wordmark in the sidebar and header:

```txt
[icon] Local AI Proxy
```

### Logo Asset

The SVG logo is saved separately as:

```txt
local-ai-proxy-logo.svg
```

A compact icon-only version is saved as:

```txt
local-ai-proxy-icon.svg
```

### Logo SVG

```svg
<svg width="128" height="128" viewBox="0 0 128 128" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Local AI Proxy Logo</title>
  <desc id="desc">A neutral geometric proxy-routing mark built from a hexagonal wireframe and internal routing lines.</desc>
  <rect width="128" height="128" rx="28" fill="#F7F5F0"/>
  <path d="M64 16L105.6 40V88L64 112L22.4 88V40L64 16Z" stroke="#111827" stroke-width="6" stroke-linejoin="round"/>
  <path d="M64 16V61.5M64 61.5V112" stroke="#111827" stroke-width="5" stroke-linecap="round"/>
  <path d="M22.4 40L64 61.5L105.6 40" stroke="#111827" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M22.4 88L64 61.5L105.6 88" stroke="#111827" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="64" cy="61.5" r="7" fill="#111827"/>
</svg>
```

---

## Color Palette

### Backgrounds

| Token | Color | Usage |
|---|---:|---|
| `bg.app` | `#FAF9F6` | Main app background |
| `bg.sidebar` | `#F3F0EA` | Sidebar background |
| `bg.card` | `#FFFFFF` | Cards, panels, table wrappers |
| `bg.card-muted` | `#F7F5F0` | Table headers, selected controls |
| `bg.hover` | `#EEEAE2` | Sidebar hover, segmented control hover |

### Text

| Token | Color | Usage |
|---|---:|---|
| `text.primary` | `#111827` | Main headings and strong text |
| `text.secondary` | `#4B5563` | Subtitles and body copy |
| `text.muted` | `#6B7280` | Labels, timestamps, table secondary text |
| `text.faint` | `#9CA3AF` | Disabled or very low-priority text |

### Borders and Lines

| Token | Color | Usage |
|---|---:|---|
| `border.default` | `#E5E1DA` | Card borders |
| `border.subtle` | `#EEEAE2` | Table row separators |
| `chart.grid` | `#DDD8CF` | Chart grid lines |

### Accents

Use accents sparingly.

| Token | Color | Usage |
|---|---:|---|
| `accent.slate` | `#64748B` | Chart bars and progress bars |
| `accent.green` | `#1F7A3F` | Healthy status, positive state |
| `accent.green-bg` | `#EAF6EE` | Success badge background |
| `accent.blue` | `#2563EB` | Completed/info state |
| `accent.blue-bg` | `#EAF1FF` | Completed badge background |
| `accent.red` | `#B42318` | Error state |
| `accent.red-bg` | `#FEF3F2` | Error badge background |
| `accent.beige` | `#EDE7DC` | Model icon background |

---

## Typography

Recommended font stack:

```css
font-family:
  Inter,
  ui-sans-serif,
  system-ui,
  -apple-system,
  BlinkMacSystemFont,
  "Segoe UI",
  sans-serif;
```

### Type Scale

| Style | Size | Weight | Line Height | Usage |
|---|---:|---:|---:|---|
| `display.page` | 32px | 700 | 40px | Main page title |
| `heading.card` | 16px | 600 | 24px | Card titles |
| `metric.large` | 30px | 700 | 36px | Big metric values |
| `body.default` | 14px | 400 | 22px | Table cells, labels |
| `body.strong` | 14px | 600 | 22px | Model names, nav labels |
| `caption` | 12px | 500 | 18px | Badges, small meta text |

---

## Layout

### App Shell

Desktop layout:

```txt
┌───────────────────┬─────────────────────────────────────────────┐
│ Sidebar           │ Main Content                                │
│ 280px             │ fluid                                       │
│                   │                                             │
│ Nav               │ Header                                      │
│                   │ Metric cards                                │
│                   │ Chart + top models                          │
│                   │ Recent requests table                       │
│ Status card       │                                             │
└───────────────────┴─────────────────────────────────────────────┘
```

Recommended measurements:

```css
--sidebar-width: 280px;
--page-padding-x: 40px;
--page-padding-y: 32px;
--card-radius: 14px;
--card-padding: 24px;
--grid-gap: 24px;
```

### Main Content Width

Use a max content width to avoid the dashboard feeling stretched on large monitors.

```css
.main-inner {
  max-width: 1440px;
  margin: 0 auto;
}
```

---

## Sidebar

### Items

Primary navigation:

```txt
Overview
Requests
Models
Providers
Costs
Settings
```

### Sidebar Behavior

- Selected item uses a soft beige/gray background.
- Icons should be simple line icons.
- Keep icon size around 20px.
- Bottom status card shows:
  - proxy status
  - running/stopped/error
  - app version

### Sidebar Status Card

Example:

```txt
● Proxy status
  Running

v1.2.0
```

States:

| State | Dot Color | Label |
|---|---:|---|
| Running | `#1F7A3F` | Running |
| Stopped | `#6B7280` | Stopped |
| Error | `#B42318` | Error |

---

## Overview Page

The overview page should answer: “What is happening right now?”

### Header

Left:
```txt
Local AI Proxy
Usage and routing overview
```

Right:
```txt
● All systems operational
Theme toggle
User avatar / local profile
```

### Metric Cards

Use exactly four cards in the first row:

1. **Total tokens today**
   - Main value: `24.7M`
   - Subtext: change vs yesterday

2. **Estimated cost**
   - Main value: `$8.62`
   - Subtext: change vs yesterday

3. **Top model**
   - Main value: `Claude 3.5 Sonnet`
   - Subtext: percent of total tokens

4. **Average latency**
   - Main value: `842 ms`
   - Subtext: change vs yesterday

Avoid adding more top cards unless there is a strong reason.

---

## Chart Panel

### Token Usage Over Time

Use a simple bar chart by default.

Chart rules:
- Muted slate bars
- Light dashed grid lines
- No heavy chart frame
- 5 to 7 y-axis labels max
- Time range selector in the top-right

Time range options:

```txt
1H  6H  24H  7D  30D
```

Default selected range:

```txt
24H
```

Chart should show usage trends, not overly detailed analytics.

---

## Top Models / Providers Panel

Show a compact ranked list.

Columns:
- model icon
- model name
- provider
- percent
- progress bar
- token total

Example rows:

```txt
Claude 3.5 Sonnet   Anthropic   43%   10.6M
GPT-4.1             OpenAI      28%   6.9M
Gemini 2.5 Pro      Gemini      17%   4.2M
Claude 3 Haiku      Anthropic   7%    1.7M
GPT-4o mini         OpenAI      5%    1.3M
```

Progress bars should be thin and muted.

---

## Recent Requests Table

The recent requests table should be practical and simple.

### Columns

```txt
Time
Client
Provider
Model
Tokens
Cost
Status
```

### Example Clients

```txt
Claude Code
OpenAI SDK
Gemini CLI
Custom App
Codex
```

### Example Providers

```txt
OpenAI
Anthropic
Gemini
OpenRouter
Ollama
LM Studio
```

### Status Badges

| Status | Style |
|---|---|
| Success | green dot, green-tinted pill |
| Completed | blue dot, blue-tinted pill |
| Error | red dot, red-tinted pill |
| Cancelled | gray dot, gray-tinted pill |

---

## Component Styling

### Card

```css
.card {
  background: #FFFFFF;
  border: 1px solid #E5E1DA;
  border-radius: 14px;
  box-shadow: 0 8px 24px rgba(17, 24, 39, 0.04);
  padding: 24px;
}
```

### Button / Segmented Control

```css
.segmented-control {
  background: transparent;
  border-radius: 999px;
}

.segmented-control-item {
  border-radius: 8px;
  padding: 6px 10px;
  color: #4B5563;
}

.segmented-control-item[data-active="true"] {
  background: #EEEAE2;
  color: #111827;
}
```

### Badge

```css
.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  font-weight: 500;
}
```

### Table

```css
.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  background: #F7F5F0;
  color: #4B5563;
  font-size: 13px;
  font-weight: 500;
  text-align: left;
  padding: 12px 20px;
}

.table td {
  border-top: 1px solid #EEEAE2;
  color: #374151;
  font-size: 14px;
  padding: 12px 20px;
}
```

---

## Dashboard Pages

### 1. Overview

Default landing page.

Shows:
- key metrics
- token usage chart
- top models/providers
- recent requests

### 2. Requests

Detailed request log.

Filters:
- provider
- model
- client
- status
- date range
- streaming/non-streaming

Useful columns:
- timestamp
- client
- endpoint
- provider
- resolved model
- input tokens
- output tokens
- cost
- latency
- status

### 3. Models

Shows model-level usage.

Metrics:
- total tokens
- total cost
- average latency
- error rate
- request count

Also show aliases:

```txt
claude-sonnet → anthropic/claude-sonnet-4
gpt          → openai/gpt-4.1
gemini       → gemini/gemini-2.5-pro
```

### 4. Providers

Shows provider health and routing.

Cards:
- OpenAI
- Anthropic
- Gemini
- OpenRouter
- Ollama
- LM Studio

Each provider card:
- status
- base URL
- default model
- requests today
- error rate
- average latency

### 5. Costs

Shows spend estimates.

Sections:
- today
- this week
- this month
- cost by provider
- cost by model

Important: mark costs as estimated when provider pricing or token counts are estimated.

### 6. Settings

Local configuration UI.

Sections:
- default provider
- default model
- model aliases
- API key environment variable names
- pricing table
- logging level
- data retention

Avoid exposing raw API keys in the UI.

---

## Data Visualization Rules

Keep charts simple.

Use:
- bar chart for tokens over time
- line chart for latency over time
- horizontal bars for model/provider share
- small stat cards for totals

Avoid:
- pie charts unless there are fewer than 5 categories
- 3D charts
- gradients
- glowing graphs
- crowded dashboards with too many panels

---

## Empty States

Use plain, helpful empty states.

Example:

```txt
No requests yet

Start the proxy and point Claude Code or an OpenAI-compatible client to your local endpoint.
```

Do not use cartoon mascots or fake AI illustrations.

---

## Error States

Errors should be visible but not dramatic.

Example:

```txt
Provider error

OpenRouter returned a 401 Unauthorized response.
Check your OPENROUTER_API_KEY environment variable.
```

Use:
- red text for critical part
- clear explanation
- exact provider name
- suggested fix

---

## Responsive Behavior

### Desktop

Full layout with sidebar and dashboard grid.

### Tablet

Sidebar can collapse to icons.
Metric cards become 2x2.

### Mobile

Mobile is lower priority, but should still work.

Suggested mobile layout:
- top nav instead of sidebar
- metric cards stacked
- chart full width
- table becomes horizontally scrollable

---

## Tailwind Theme Tokens

Suggested Tailwind extension:

```js
theme: {
  extend: {
    colors: {
      app: {
        bg: "#FAF9F6",
        sidebar: "#F3F0EA",
        card: "#FFFFFF",
        muted: "#F7F5F0",
        hover: "#EEEAE2",
      },
      ink: {
        primary: "#111827",
        secondary: "#4B5563",
        muted: "#6B7280",
        faint: "#9CA3AF",
      },
      line: {
        default: "#E5E1DA",
        subtle: "#EEEAE2",
      },
      status: {
        success: "#1F7A3F",
        successBg: "#EAF6EE",
        info: "#2563EB",
        infoBg: "#EAF1FF",
        error: "#B42318",
        errorBg: "#FEF3F2",
      },
      chart: {
        bar: "#64748B",
        grid: "#DDD8CF",
      },
    },
    borderRadius: {
      card: "14px",
      panel: "18px",
    },
    boxShadow: {
      card: "0 8px 24px rgba(17, 24, 39, 0.04)",
    },
  },
}
```

---

## Suggested React Component Names

```txt
AppShell
Sidebar
SidebarItem
ProxyStatusCard
DashboardHeader
MetricCard
TokenUsageChart
TopModelsCard
RecentRequestsTable
StatusBadge
TimeRangeSelector
ProviderIcon
ModelAliasRow
```

---

## Implementation Notes

Recommended frontend stack:

```txt
Next.js
React
Tailwind CSS
shadcn/ui
lucide-react
Recharts
```

Recommended backend stats endpoints:

```txt
GET /dashboard/stats/overview
GET /dashboard/stats/tokens
GET /dashboard/stats/models
GET /dashboard/requests/recent
GET /dashboard/providers
GET /dashboard/settings
PATCH /dashboard/settings
```

The dashboard should read from the FastAPI proxy database, not from provider APIs directly.

---

## MVP Dashboard Scope

Build this first:

```txt
Overview page
Recent requests table
Token usage chart
Top models/providers card
Basic settings page for default provider/model
```

Leave these for later:

```txt
Advanced filtering
Provider health checks
Cost forecasting
Export CSV
User profiles
Hosted sync
```

---

## Final Visual Summary

The design should feel like:

```txt
quiet
local-first
spacious
developer-focused
neutral
practical
fast
```

It should not feel like:

```txt
flashy
futuristic
crowded
generic AI SaaS
over-animated
decorative for no reason
```
