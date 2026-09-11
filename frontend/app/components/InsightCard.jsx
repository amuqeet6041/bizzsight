"use client";

// Reusable business insight card backed by one structured_insights object:
// { type, priority, title, message, metric, value, severity }.
// Unknown severities / priorities fall back to a neutral style.

const SEVERITY_STYLES = {
  positive:
    "border-emerald-400/20 bg-emerald-400/[0.04]",
  negative:
    "border-red-400/20 bg-red-400/[0.04]",
  warning:
    "border-amber-400/20 bg-amber-400/[0.04]",
  informational:
    "border-white/10 bg-[#0D1117]",
  neutral:
    "border-white/10 bg-[#0D1117]",
};

const SEVERITY_BADGES = {
  positive: "bg-emerald-400/10 text-emerald-300 border-emerald-400/30",
  negative: "bg-red-400/10 text-red-300 border-red-400/30",
  warning: "bg-amber-400/10 text-amber-300 border-amber-400/30",
  informational: "bg-white/5 text-gray-300 border-white/10",
  neutral: "bg-white/5 text-gray-300 border-white/10",
};

const SEVERITY_LABELS = {
  positive: "Positive",
  negative: "Risk",
  warning: "Warning",
  informational: "Observation",
  neutral: "Observation",
};

const PRIORITY_BADGES = {
  high: "bg-red-400/10 text-red-300 border-red-400/30",
  medium: "bg-amber-400/10 text-amber-300 border-amber-400/30",
  low: "bg-white/5 text-gray-300 border-white/10",
};

export default function InsightCard({ insight }) {
  if (!insight) return null;

  const severity = insight.severity || "neutral";
  const severityKey = SEVERITY_STYLES[severity]
    ? severity
    : "neutral";

  return (
    <div
      className={`rounded-xl border px-5 py-4 ${
        SEVERITY_STYLES[severityKey]
      }`}
    >
      <div className="flex flex-wrap items-center gap-2 mb-2">
        {insight.priority && (
          <span
            className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
              PRIORITY_BADGES[insight.priority] ||
              PRIORITY_BADGES.low
            } uppercase tracking-wide`}
          >
            {insight.priority}
          </span>
        )}

        {severity && (
          <span
            className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
              SEVERITY_BADGES[severityKey]
            } uppercase tracking-wide`}
          >
            {SEVERITY_LABELS[severityKey]}
          </span>
        )}
      </div>

      {insight.title && (
        <p className="text-sm font-semibold text-white">
          {insight.title}
        </p>
      )}

      {insight.message && (
        <p className="text-sm text-gray-400 mt-1.5">
          {insight.message}
        </p>
      )}

      {insight.metric && (
        <p className="text-xs text-gray-500 mt-2">
          Metric: <span className="text-gray-300">{insight.metric}</span>
        </p>
      )}
    </div>
  );
}