// Shared formatting helpers for the BizSight results dashboard.
//
// The backend is the source of truth for numbers. These helpers only turn
// backend values into display strings and NEVER invent replacement values for
// missing data (null always stays visually honest).

// Value formats used by the backend chart_specs / metrics.
export const FORMAT_CURRENCY = "currency";
export const FORMAT_COUNT = "count";
export const FORMAT_PERCENT = "percent";

export function toFinite(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}

export function formatCompact(value) {
  const num = toFinite(value);
  if (num === null) return "";
  const abs = Math.abs(num);
  if (abs >= 1000000) return `${(num / 1000000).toFixed(1)}M`;
  if (abs >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return `${Math.round(num)}`;
}

export function formatMoney(value) {
  const num = toFinite(value);
  if (num === null) return null;
  return `$${num.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function formatCount(value) {
  const num = toFinite(value);
  if (num === null) return null;
  return num.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

// Backend fractions (e.g. 0.3333) are displayed as percentages (e.g. 33.3%).
export function formatPercent(value, digits = 1) {
  const num = toFinite(value);
  if (num === null) return null;
  return `${(num * 100).toFixed(digits)}%`;
}

// Format a backend metric value based on its value_format. Never renders 0 for
// null — callers must decide how to render null (e.g. "Not available").
export function formatValueByFormat(value, format) {
  if (value === null || value === undefined) return null;
  if (format === FORMAT_CURRENCY) return formatMoney(value);
  if (format === FORMAT_PERCENT) return formatPercent(value);
  return formatCount(value);
}

// Tooltip / axis formatter that always returns a string.
export function formatChartValue(value, format) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return "";
  if (format === FORMAT_CURRENCY) return formatMoney(value) || "";
  if (format === FORMAT_PERCENT) return formatPercent(value) || "";
  const str = formatCount(value);
  return str === null ? String(value) : str;
}

// Display format for a backend metric key (UI display choice only — the
// numeric value itself always comes from the backend).
const METRIC_DISPLAY_FORMAT = {
  revenue: FORMAT_CURRENCY,
  cogs: FORMAT_CURRENCY,
  shipping: FORMAT_CURRENCY,
  marketing: FORMAT_CURRENCY,
  gross_profit: FORMAT_CURRENCY,
  net_profit: FORMAT_CURRENCY,
  orders: FORMAT_COUNT,
  quantity: FORMAT_COUNT,
  average_order_value: FORMAT_CURRENCY,
  customer_acquisition_cost: FORMAT_CURRENCY,
  gross_profit_margin: FORMAT_PERCENT,
  net_profit_margin: FORMAT_PERCENT,
  repeat_purchase_rate: FORMAT_PERCENT,
  return_cancel_rate: FORMAT_PERCENT,
};

export function metricDisplayFormat(metricKey) {
  return METRIC_DISPLAY_FORMAT[metricKey] || FORMAT_COUNT;
}