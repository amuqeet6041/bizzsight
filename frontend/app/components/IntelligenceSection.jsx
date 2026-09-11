"use client";

import BusinessAdvisor from "./BusinessAdvisor";
import BackendMetricCard from "./BackendMetricCard";
import InsightCard from "./InsightCard";

// Phase 8 "Business Intelligence" section.
//
// Drives the results panel from the backend contract (metric_values,
// metric_status, metric_definitions, structured_insights + insight_summary,
// and the AI advisor). Legacy `insights` (flat strings) is used only as a
// fallback when structured_insights is missing/empty.

const CATEGORY_ORDER = [
  "financial",
  "customer",
  "operations",
  "product",
  "geography",
];

const CATEGORY_LABELS = {
  financial: "Financial",
  customer: "Customer",
  operations: "Operations",
  product: "Product",
  geography: "Geography",
};

const INSIGHT_LABELS = {
  total: "Total",
  high_priority: "High priority",
  warnings: "Warnings",
};

export default function IntelligenceSection({ resultData }) {
  const metricValues = resultData?.metric_values || {};
  const metricStatus = resultData?.metric_status || {};
  const metricDefinitions = resultData?.metric_definitions || {};
  const advisor = resultData?.advisor;
  const fieldsPresent = resultData?.fields_present || {};

  const structuredInsights = Array.isArray(resultData?.structured_insights)
    ? resultData.structured_insights
    : [];
  const legacyInsights = Array.isArray(resultData?.insights)
    ? resultData.insights
    : [];
  const insightSummary = resultData?.insight_summary || {};

  const usesFallbackInsights =
    structuredInsights.length === 0 && legacyInsights.length > 0;

  const insightCards =
    structuredInsights.length > 0
      ? structuredInsights
      : legacyInsights.map((message) => ({
          title: null,
          message,
          severity: "neutral",
        }));

  // Preserve backend metric order (metric_status reflects METRIC_DEFINITIONS
  // insertion order) while grouping by category.
  const metricsByCategory = {};
  Object.entries(metricStatus).forEach(([key, entry]) => {
    const category = entry?.category || "financial";
    if (!metricsByCategory[category]) metricsByCategory[category] = [];
    metricsByCategory[category].push(key);
  });

  const orderedCategories = CATEGORY_ORDER.filter(
    (category) =>
      metricsByCategory[category] &&
      metricsByCategory[category].length > 0
  );

  const summaryChips = Object.entries(insightSummary).filter(
    ([key]) => INSIGHT_LABELS[key]
  );

  return (
    <div>
      {/* ==================================================
          AI BUSINESS ADVISOR
      ================================================== */}
      <BusinessAdvisor advisor={advisor} />

      {/* ==================================================
          KEY METRICS (backend metric_values + metric_status)
      ================================================== */}
      <div className="mt-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400" />
          <h2 className="text-xl font-semibold">Key Metrics</h2>
        </div>

        <p className="text-sm text-gray-500 mb-5 max-w-2xl">
          Every metric is calculated by BizSight from the data that was actually
          delivered. Metrics that cannot be verified show{" "}
          <span className="text-amber-300">Not Available</span> — they are never
          reported as zero.
        </p>

        {orderedCategories.length > 0 ? (
          orderedCategories.map((category) => (
            <div key={category} className="mb-6">
              <p className="text-xs font-medium text-gray-500 mb-3 uppercase tracking-wide">
                {CATEGORY_LABELS[category] || category}
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                {metricsByCategory[category].map((key) => (
                  <BackendMetricCard
                    key={key}
                    metricKey={key}
                    value={metricValues[key]}
                    statusEntry={metricStatus[key]}
                    definition={metricDefinitions[key]}
                  />
                ))}
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-white/10 bg-[#0D1117] px-5 py-6 text-sm text-gray-400">
            No metrics are available for this dataset.
          </div>
        )}

        {fieldsPresent.has_date === false && (
          <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-4 text-sm text-gray-400">
            No date field was detected — time-based metrics and trends are not
            available for this dataset.
          </div>
        )}
      </div>

      {/* ==================================================
          BUSINESS INSIGHTS (structured_insights)
      ================================================== */}
      <div className="mt-8">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-2 h-2 rounded-full bg-emerald-400" />
          <h2 className="text-xl font-semibold">Business Insights</h2>
        </div>

        {summaryChips.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 mb-5">
            {summaryChips.map(([key, value]) => (
              <span
                key={key}
                className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-[#0D1117] px-3 py-1.5 text-xs text-gray-400"
              >
                <span className="font-semibold text-white">{value}</span>
                {INSIGHT_LABELS[key]}
              </span>
            ))}
          </div>
        )}

        {usesFallbackInsights && (
          <p className="text-xs text-gray-600 mb-3">
            Showing the original insight list — structured insights are not
            present in this response.
          </p>
        )}

        {insightCards.length > 0 ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            {insightCards.map((insight, index) => (
              <InsightCard key={index} insight={insight} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-white/10 bg-[#0D1117] px-5 py-6 text-sm text-gray-400">
            No additional business insights are available.
          </div>
        )}
      </div>
    </div>
  );
}