export default function Features() {
  const features = [
    {
      number: "01",
      title: "Automatic Data Cleaning",
      description:
        "Upload your business data and let BizSight handle duplicates, missing values, irrelevant columns, and inconsistent data automatically.",
      icon: (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M4 12L7 15L13 9"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M13 15L16 18L21 13"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M3 5H21"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M3 19H9"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        </svg>
      ),
    },

    {
      number: "02",
      title: "Revenue & Profit Analysis",
      description:
        "See your revenue, profit, margins, and financial performance in one place with calculations generated directly from your business data.",
      icon: (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M4 19V5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M4 19H20"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M7 15L10 11L13 13L18 7"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M15 7H18V10"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ),
    },

    {
      number: "03",
      title: "Expense Intelligence",
      description:
        "Break down your expenses, identify major cost drivers, and understand exactly where your business money is being spent.",
      icon: (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <rect
            x="3"
            y="5"
            width="18"
            height="14"
            rx="2"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <path
            d="M7 9H17"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M7 13H12"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <circle
            cx="17"
            cy="14"
            r="1.5"
            fill="currentColor"
          />
        </svg>
      ),
    },

    {
      number: "04",
      title: "Sales & Customer Analytics",
      description:
        "Understand your sales patterns, customer behavior, product performance, and the trends that are shaping your business.",
      icon: (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <circle
            cx="9"
            cy="8"
            r="3"
            stroke="currentColor"
            strokeWidth="1.8"
          />
          <path
            d="M3.5 19C3.5 15.96 5.96 13.5 9 13.5C12.04 13.5 14.5 15.96 14.5 19"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M15 11C17.21 11 19 12.79 19 15"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M17 6.5C18.66 6.5 20 7.84 20 9.5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        </svg>
      ),
    },

    {
      number: "05",
      title: "Advanced Business Analytics",
      description:
        "Go beyond basic numbers with statistical analysis, KPIs, trends, correlations, and deeper insights hidden inside your data.",
      icon: (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M4 18L9 13L13 16L20 8"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M16 8H20V12"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle
            cx="4"
            cy="18"
            r="1.5"
            fill="currentColor"
          />
          <circle
            cx="9"
            cy="13"
            r="1.5"
            fill="currentColor"
          />
          <circle
            cx="13"
            cy="16"
            r="1.5"
            fill="currentColor"
          />
        </svg>
      ),
    },

    {
      number: "06",
      title: "AI-Powered Recommendations",
      description:
        "Turn analysis into action with intelligent recommendations designed to help you make better business and financial decisions.",
      icon: (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M12 3L13.7 8.3L19 10L13.7 11.7L12 17L10.3 11.7L5 10L10.3 8.3L12 3Z"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          />
          <path
            d="M19 15L19.8 17.2L22 18L19.8 18.8L19 21L18.2 18.8L16 18L18.2 17.2L19 15Z"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </svg>
      ),
    },
  ];

  return (
    <section
      id="features"
      className="relative overflow-hidden border-t border-white/[0.06] bg-[#070A0D] py-16 sm:py-20 lg:py-24"
    >
      {/* Background Glow */}
      <div className="pointer-events-none absolute left-1/2 top-0 h-[500px] w-[700px] -translate-x-1/2 rounded-full bg-emerald-500/[0.05] blur-[120px]" />

      {/* Content */}
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">

        {/* Section Header */}
        <div className="mx-auto max-w-3xl text-center">

          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.06] px-3.5 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />

            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-400">
              Powerful Intelligence
            </span>
          </div>

          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl lg:text-5xl">
            Everything you need to{" "}
            <span className="text-emerald-400">
              understand your business.
            </span>
          </h2>

          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">
            BizSight transforms your raw business data into meaningful
            financial, statistical, and operational insights — without
            requiring you to be a data expert.
          </p>
        </div>

        {/* Feature Grid */}
        <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">

          {features.map((feature) => (
            <div
              key={feature.number}
              className="group relative overflow-hidden rounded-2xl border border-white/[0.07] bg-white/[0.025] p-7 transition-all duration-300 hover:-translate-y-1 hover:border-emerald-400/20 hover:bg-white/[0.04]"
            >

              {/* Card Glow */}
              <div className="pointer-events-none absolute -right-20 -top-20 h-40 w-40 rounded-full bg-emerald-400/[0.07] blur-3xl opacity-0 transition-opacity duration-500 group-hover:opacity-100" />

              {/* Number */}
              <div className="absolute right-6 top-6 text-xs font-semibold tracking-widest text-slate-700 transition-colors duration-300 group-hover:text-emerald-400/40">
                {feature.number}
              </div>

              {/* Icon */}
              <div className="relative flex h-12 w-12 items-center justify-center rounded-xl border border-emerald-400/15 bg-emerald-400/[0.07] text-emerald-400 transition-all duration-300 group-hover:border-emerald-400/30 group-hover:bg-emerald-400/10">
                {feature.icon}
              </div>

              {/* Text */}
              <div className="relative mt-6">
                <h3 className="text-lg font-semibold text-white">
                  {feature.title}
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-400">
                  {feature.description}
                </p>
              </div>

              {/* Bottom Accent */}
              <div className="absolute bottom-0 left-0 h-px w-0 bg-emerald-400 transition-all duration-500 group-hover:w-full" />
            </div>
          ))}
        </div>

        {/* Bottom Statement */}
        <div className="mt-10 flex justify-center">
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span className="h-px w-8 bg-white/[0.08]" />

            <span>
              From raw data to{" "}
              <span className="font-medium text-slate-300">
                business decisions
              </span>
            </span>

            <span className="h-px w-8 bg-white/[0.08]" />
          </div>
        </div>

      </div>
    </section>
  );
}