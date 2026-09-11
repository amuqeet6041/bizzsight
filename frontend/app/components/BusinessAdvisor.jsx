"use client";

// AI Business Advisor section. Renders the backend `advisor` response
// verbatim — no numbers are calculated or rewritten in the frontend.
//
// - advisor.status === "AVAILABLE"   -> full report
// - advisor.status === "UNAVAILABLE" -> graceful message, never fake advice

const HEALTH_STYLES = {
  positive: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  mixed: "border-amber-400/30 bg-amber-400/10 text-amber-300",
  negative: "border-red-400/30 bg-red-400/10 text-red-300",
};

const HEALTH_LABELS = {
  positive: "Positive",
  mixed: "Mixed",
  negative: "Negative",
};

const SECTION_LABELS = {
  priorities: "Priorities",
  opportunities: "Opportunities",
  risks: "Risks",
  observations: "Observations",
};

function capitalize(value) {
  if (typeof value !== "string" || !value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function renderAdviceSection(title, items, renderItem) {
  if (!Array.isArray(items) || items.length === 0) return null;

  return (
    <div className="mt-6">
      <h3 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wide">
        {title}
      </h3>

      <div className="space-y-3">
        {items.map((item, index) => renderItem(item, index))}
      </div>
    </div>
  );
}

function AdviceCard({ children, accent }) {
  return (
    <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-4">
      {children}
    </div>
  );
}

function ItemHeading({ title }) {
  if (!title) return null;
  return <p className="text-sm font-semibold text-white">{title}</p>;
}

function ItemLine({ label, text }) {
  if (!text) return null;
  return (
    <p className="text-sm text-gray-400 mt-1.5">
      <span className="text-gray-500">{label}</span> {text}
    </p>
  );
}

export default function BusinessAdvisor({ advisor }) {
  if (!advisor || advisor.status !== "AVAILABLE") {
    return (
      <section className="rounded-2xl border border-white/10 bg-[#0D1117] p-7">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
            🧠
          </div>
          <div>
            <h2 className="text-xl font-semibold">AI Business Advisor</h2>
            <p className="text-sm text-gray-500 mt-1">
              Genuine business guidance for your dataset
            </p>
          </div>
        </div>

        <div className="rounded-xl border border-white/10 bg-[#070A0D] px-5 py-6 text-sm text-gray-400">
          <p>Business Advisor is currently unavailable.</p>
          {advisor?.reason && advisor.reason !== "Business advisor is currently unavailable." && (
            <p className="text-gray-500 mt-1">{advisor.reason}</p>
          )}
        </div>
      </section>
    );
  }

  const health = advisor.health || {};
  const overall = health.overall || "neutral";
  const healthStyle = HEALTH_STYLES[overall] || HEALTH_STYLES.mixed;
  const healthLabel =
    HEALTH_LABELS[overall] || capitalize(overall);

  return (
    <section className="rounded-2xl border border-emerald-400/20 bg-emerald-400/[0.03] p-7">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-xl bg-emerald-400/10 border border-emerald-400/20 flex items-center justify-center">
          🧠
        </div>
        <div className="flex-1">
          <h2 className="text-xl font-semibold">AI Business Advisor</h2>
          <p className="text-sm text-gray-500 mt-1">
            Verified guidance generated from your data
          </p>
        </div>
        {advisor.prompt_version && (
          <span className="text-xs text-gray-600">
            {advisor.prompt_version}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="rounded-xl border border-white/10 bg-[#0D1117] px-5 py-4">
          <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">
            Overall Business Health
          </p>
          <span
            className={`inline-flex items-center rounded-lg border px-3 py-1 text-sm font-semibold ${healthStyle}`}
          >
            {healthLabel}
          </span>
          {health.explanation && (
            <p className="text-sm text-gray-400 mt-3">
              {health.explanation}
            </p>
          )}
        </div>

        <div className="rounded-xl border border-white/10 bg-[#0D1117] px-5 py-4">
          <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">
            Summary
          </p>
          <p className="text-sm text-gray-300 leading-relaxed">
            {advisor.summary}
          </p>
        </div>
      </div>

      {renderAdviceSection(
        SECTION_LABELS.priorities,
        advisor.priorities,
        (item, index) => (
          <AdviceCard key={item.title || `p-${index}`}>
            <div className="flex items-center justify-between gap-3">
              <ItemHeading title={item.title} />
              <div className="flex items-center gap-1.5">
                {["priority", "impact", "effort"].map((key) =>
                  item[key] ? (
                    <span
                      key={key}
                      className="inline-flex items-center rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-xs text-gray-300"
                    >
                      {item[key]}
                    </span>
                  ) : null
                )}
              </div>
            </div>
            <ItemLine label="Why" text={item.reason} />
            <ItemLine label="Action" text={item.action} />
          </AdviceCard>
        )
      )}

      {renderAdviceSection(
        SECTION_LABELS.opportunities,
        advisor.opportunities,
        (item, index) => (
          <AdviceCard key={item.title || `o-${index}`}>
            <ItemHeading title={item.title} />
            <ItemLine label="" text={item.explanation} />
            <ItemLine label="Action" text={item.action} />
          </AdviceCard>
        )
      )}

      {renderAdviceSection(
        SECTION_LABELS.risks,
        advisor.risks,
        (item, index) => (
          <AdviceCard key={item.title || `r-${index}`}>
            <ItemHeading title={item.title} />
            <ItemLine label="" text={item.explanation} />
            <ItemLine label="Action" text={item.action} />
          </AdviceCard>
        )
      )}

      {renderAdviceSection(
        SECTION_LABELS.observations,
        advisor.observations,
        (item, index) => (
          <AdviceCard key={item.title || `obs-${index}`}>
            <ItemHeading title={item.title} />
            <ItemLine label="" text={item.message} />
          </AdviceCard>
        )
      )}

      {Array.isArray(advisor.data_limitations) &&
        advisor.data_limitations.length > 0 && (
          <div className="mt-6 rounded-xl border border-white/10 bg-[#070A0D] px-5 py-4">
            <p className="text-xs text-gray-500 mb-2 uppercase tracking-wide">
              Data Limitations
            </p>
            <ul className="space-y-1.5">
              {advisor.data_limitations.map((limitation, index) => (
                <li
                  key={index}
                  className="text-sm text-gray-400 flex gap-2"
                >
                  <span className="text-gray-600">•</span>
                  <span>{limitation}</span>
                </li>
              ))}
            </ul>
            <p className="text-xs text-gray-600 mt-3">
              These are limitations of the available dataset, not a reflection
              of business performance.
            </p>
          </div>
        )}
    </section>
  );
}