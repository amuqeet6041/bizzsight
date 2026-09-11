"use client";

import DynamicChart from "./DynamicChart";

// Renders a group of chart specs under one category heading.

const CATEGORY_LABELS = {
  financial: "Financial Analysis",
  product: "Product Analysis",
  customer: "Customer Analysis",
  geography: "Geography",
  operations: "Operations",
};

function isFullWidth(spec) {
  // Financial trend / margin lines read better at full width.
  return (
    spec.category === "financial" &&
    spec.type === "line"
  );
}

export default function ChartSection({
  category,
  specs,
}) {
  const label =
    CATEGORY_LABELS[category] ||
    category.charAt(0).toUpperCase() + category.slice(1);

  return (
    <section className="mb-10">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-2 h-2 rounded-full bg-emerald-400" />
        <h3 className="text-lg font-semibold text-white">
          {label}
        </h3>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {specs.map((spec) => (
          <div
            key={spec.id}
            className={`rounded-2xl border border-white/10 bg-[#0D1117] p-7 ${
              isFullWidth(spec) ? "lg:col-span-2" : ""
            }`}
          >
            <div className="mb-6">
              <h4 className="text-xl font-semibold">
                {spec.title}
              </h4>

              {spec.description && (
                <p className="text-sm text-gray-500 mt-1">
                  {spec.description}
                </p>
              )}
            </div>

            <DynamicChart spec={spec} height={300} />
          </div>
        ))}
      </div>
    </section>
  );
}