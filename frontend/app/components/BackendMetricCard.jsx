"use client";

import {
  metricDisplayFormat,
  formatValueByFormat,
} from "./formatting";

// Reusable metric card driven by backend metric_values + metric_status.
//
// AVAILABLE metrics show their backend value with a description.
// NOT_AVAILABLE metrics show an explicit "Not Available" state with the
// backend reason — they are NEVER rendered as 0 / $0 / 0%.

const AVAILABLE_BORDER = "border-white/10 hover:border-white/20";
const UNAVAILABLE_BORDER = "border-white/10";

export default function BackendMetricCard({
  metricKey,
  value,
  statusEntry,
  definition,
}) {
  const status = statusEntry?.status || "NOT_AVAILABLE";
  const isAvailable = status === "AVAILABLE";
  const label =
    statusEntry?.label || definition?.label || metricKey;
  const description =
    statusEntry?.description || definition?.description || "";
  const format = metricDisplayFormat(metricKey);

  return (
    <div
      className={`rounded-2xl border bg-[#0D1117] p-6 transition ${
        isAvailable ? AVAILABLE_BORDER : UNAVAILABLE_BORDER
      }`}
    >
      <p className="text-sm text-gray-400">{label}</p>

      {isAvailable && value !== null && value !== undefined ? (
        <>
          <h3 className="text-3xl font-semibold mt-3 break-words text-white">
            {formatValueByFormat(value, format)}
          </h3>

          <p className="text-sm mt-3 text-gray-500 line-clamp-3">
            {description}
          </p>
        </>
      ) : (
        <>
          <div className="mt-3">
            <span className="inline-flex items-center rounded-md border border-amber-400/30 bg-amber-400/10 px-2.5 py-1 text-xs font-medium text-amber-300">
              Not Available
            </span>
          </div>

          <p className="text-sm text-gray-500 mt-3">
            {statusEntry?.reason ||
              definition?.description ||
              "Required data was not detected in this dataset."}
          </p>
        </>
      )}
    </div>
  );
}