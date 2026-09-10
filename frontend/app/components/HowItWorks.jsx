export default function HowItWorks() {
  const steps = [
    {
      number: "01",
      title: "Upload Your Data",
      description:
        "Upload your business data in Excel or CSV format. BizSight works with the data you already have.",
      icon: (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M12 16V4"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M7 9L12 4L17 9"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M5 20H19"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        </svg>
      ),
    },

    {
      number: "02",
      title: "BizSight Cleans & Analyzes",
      description:
        "Your data is automatically cleaned, organized, and analyzed to uncover financial, statistical, and business insights.",
      icon: (
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M4 6H20"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M4 12H20"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <path
            d="M4 18H14"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
          <circle
            cx="18"
            cy="18"
            r="2"
            stroke="currentColor"
            strokeWidth="1.8"
          />
        </svg>
      ),
    },

    {
      number: "03",
      title: "Get Business Intelligence",
      description:
        "Explore your dashboards, financial metrics, advanced analytics, and AI-powered recommendations — all in one place.",
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
  ];

  return (
    <section
      id="how-it-works"
      className="relative overflow-hidden border-t border-white/[0.06] bg-[#070A0D] py-16 sm:py-20 lg:py-24"
    >
      {/* Background Glow */}
      <div className="pointer-events-none absolute left-1/2 top-0 h-[450px] w-[650px] -translate-x-1/2 rounded-full bg-emerald-500/[0.04] blur-[120px]" />

      {/* Content */}
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">

        {/* Section Header */}
        <div className="mx-auto max-w-3xl text-center">

          <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.06] px-3.5 py-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]" />

            <span className="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-400">
              Simple Process
            </span>
          </div>

          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl lg:text-5xl">
            From raw data to{" "}
            <span className="text-emerald-400">
              business intelligence.
            </span>
          </h2>

          <p className="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-400 sm:text-lg">
            No complicated spreadsheets. No manual calculations. Just upload
            your data and let BizSight do the heavy lifting.
          </p>
        </div>

        {/* Steps */}
        <div className="relative mt-12 grid gap-5 md:grid-cols-3">

          {/* Connecting Line */}
          <div className="pointer-events-none absolute left-[16.66%] right-[16.66%] top-12 hidden h-px bg-gradient-to-r from-transparent via-emerald-400/20 to-transparent md:block" />

          {steps.map((step) => (
            <div
              key={step.number}
              className="group relative"
            >
              {/* Number / Icon */}
              <div className="relative mx-auto flex h-24 w-24 items-center justify-center rounded-2xl border border-emerald-400/15 bg-[#0A0F0D] text-emerald-400 shadow-[0_0_30px_rgba(52,211,153,0.05)] transition-all duration-300 group-hover:border-emerald-400/30 group-hover:shadow-[0_0_35px_rgba(52,211,153,0.1)]">
                
                <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-emerald-400/15 bg-emerald-400/[0.07]">
                  {step.icon}
                </div>

                <span className="absolute -right-2 -top-2 flex h-7 w-7 items-center justify-center rounded-full border border-emerald-400/20 bg-[#070A0D] text-[10px] font-bold text-emerald-400">
                  {step.number}
                </span>
              </div>

              {/* Text */}
              <div className="mx-auto mt-6 max-w-sm text-center">
                <h3 className="text-lg font-semibold text-white">
                  {step.title}
                </h3>

                <p className="mt-3 text-sm leading-6 text-slate-400">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>

        {/* Bottom Statement */}
        <div className="mt-10 flex justify-center">
          <div className="flex items-center gap-3 text-sm text-slate-500">
            <span className="h-px w-8 bg-white/[0.08]" />

            <span>
              One upload.{" "}
              <span className="font-medium text-slate-300">
                Complete business intelligence.
              </span>
            </span>

            <span className="h-px w-8 bg-white/[0.08]" />
          </div>
        </div>

      </div>
    </section>
  );
}