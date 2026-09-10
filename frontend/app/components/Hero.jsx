"use client";

import Link from "next/link";

export default function Hero() {
  // Smooth scroll to How It Works
  const scrollToHowItWorks = () => {
    const section = document.getElementById("how-it-works");

    if (!section) return;

    const navbarHeight = 80;
    const startPosition = window.scrollY;

    const targetPosition =
      section.getBoundingClientRect().top +
      window.scrollY -
      navbarHeight;

    const distance = targetPosition - startPosition;
    const duration = 1000;

    let startTime = null;

    const easeInOutCubic = (t) => {
      return t < 0.5
        ? 4 * t * t * t
        : 1 - Math.pow(-2 * t + 2, 3) / 2;
    };

    const animateScroll = (currentTime) => {
      if (startTime === null) {
        startTime = currentTime;
      }

      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const easedProgress = easeInOutCubic(progress);

      window.scrollTo(
        0,
        startPosition + distance * easedProgress
      );

      if (progress < 1) {
        requestAnimationFrame(animateScroll);
      }
    };

    requestAnimationFrame(animateScroll);
  };

  return (
    <section className="relative overflow-hidden bg-[#070A0D] pt-32 pb-20 sm:pt-36 sm:pb-24 lg:pt-40 lg:pb-28">

      {/* ==================== BACKGROUND GLOW ==================== */}
      <div className="pointer-events-none absolute inset-0">

        {/* Main glow */}
        <div className="absolute left-1/2 top-[-200px] h-[500px] w-[700px] -translate-x-1/2 rounded-full bg-emerald-500/[0.08] blur-[120px]" />

        {/* Side glow */}
        <div className="absolute right-[-200px] top-[300px] h-[400px] w-[400px] rounded-full bg-teal-500/[0.05] blur-[100px]" />

        {/* Grid */}
        <div
          className="absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
            backgroundSize: "60px 60px",
          }}
        />
      </div>

      {/* ==================== CONTENT ==================== */}
      <div className="relative mx-auto max-w-7xl px-6 lg:px-8">

        <div className="grid items-center gap-14 lg:grid-cols-[0.95fr_1.05fr] lg:gap-16">

          {/* ==================== LEFT CONTENT ==================== */}
          <div className="max-w-2xl">

            {/* Badge */}
            <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.06] px-3.5 py-2">

              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>

              <span className="text-xs font-medium tracking-wide text-emerald-300">
                AI-Powered Business Intelligence
              </span>

            </div>

            {/* Main Heading */}
            <h1 className="text-5xl font-bold leading-[1.05] tracking-[-0.04em] text-white sm:text-6xl lg:text-7xl">

              Your business data
              <br />

              <span className="bg-gradient-to-r from-emerald-300 via-emerald-400 to-teal-400 bg-clip-text text-transparent">
                has answers.
              </span>

            </h1>

            {/* Description */}
            <p className="mt-7 max-w-xl text-base leading-7 text-slate-400 sm:text-lg">
              BizSight transforms messy business data into clear financial
              insights, powerful analytics, and actionable decisions —
              automatically.
            </p>

            {/* ==================== CTA BUTTONS ==================== */}
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">

              {/* Primary CTA */}
              <Link
                href="/analyze"
                className="group inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-500 px-6 py-3.5 text-sm font-semibold text-[#06100A] shadow-xl shadow-emerald-500/10 transition-all duration-300 hover:-translate-y-0.5 hover:bg-emerald-400 hover:shadow-emerald-400/20"
              >
                Analyze Your Data

                <svg
                  width="17"
                  height="17"
                  viewBox="0 0 24 24"
                  fill="none"
                  className="transition-transform duration-200 group-hover:translate-x-1"
                >
                  <path
                    d="M5 12H19M13 6L19 12L13 18"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </Link>

              {/* Secondary CTA */}
              <button
                type="button"
                onClick={scrollToHowItWorks}
                className="inline-flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-white/[0.1] bg-white/[0.03] px-6 py-3.5 text-sm font-medium text-slate-200 transition-all duration-300 hover:border-white/[0.16] hover:bg-white/[0.06]"
              >
                See How It Works

                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <path
                    d="M6 9L12 15L18 9"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </button>

            </div>

            {/* ==================== TRUST INDICATORS ==================== */}
            <div className="mt-10 flex flex-wrap items-center gap-x-6 gap-y-3 border-t border-white/[0.06] pt-6">

              <div className="flex items-center gap-2">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  className="text-emerald-400"
                >
                  <path
                    d="M5 12.5L9.5 17L19 7"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>

                <span className="text-xs text-slate-500">
                  Automated Data Cleaning
                </span>
              </div>

              <div className="flex items-center gap-2">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  className="text-emerald-400"
                >
                  <path
                    d="M5 12.5L9.5 17L19 7"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>

                <span className="text-xs text-slate-500">
                  Financial Analytics
                </span>
              </div>

              <div className="flex items-center gap-2">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  className="text-emerald-400"
                >
                  <path
                    d="M5 12.5L9.5 17L19 7"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>

                <span className="text-xs text-slate-500">
                  AI Insights
                </span>
              </div>

            </div>

          </div>

          {/* ==================== RIGHT DASHBOARD PREVIEW ==================== */}
          <div className="relative mx-auto w-full max-w-2xl lg:max-w-none">

            {/* Glow behind dashboard */}
            <div className="absolute left-1/2 top-1/2 h-[300px] w-[500px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-500/[0.07] blur-[100px]" />

            {/* Dashboard Window */}
            <div className="relative overflow-hidden rounded-2xl border border-white/[0.1] bg-[#0C1116] shadow-2xl shadow-black/40">

              {/* Window Header */}
              <div className="flex items-center justify-between border-b border-white/[0.07] px-4 py-3">

                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" />
                  <span className="h-2.5 w-2.5 rounded-full bg-yellow-400/70" />
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
                </div>

                <div className="rounded-md border border-white/[0.06] bg-white/[0.03] px-3 py-1">
                  <span className="text-[10px] text-slate-500">
                    BizSight Analytics
                  </span>
                </div>

                <div className="h-5 w-5 rounded-md bg-white/[0.04]" />

              </div>

              {/* Dashboard Content */}
              <div className="p-4 sm:p-5">

                {/* Dashboard Title */}
                <div className="mb-5 flex items-center justify-between">

                  <div>
                    <p className="text-[10px] uppercase tracking-wider text-slate-500">
                      Business Overview
                    </p>

                    <h3 className="mt-1 text-base font-semibold text-white">
                      Financial Performance
                    </h3>
                  </div>

                  <div className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5">
                    <span className="text-[10px] text-slate-400">
                      Last 30 days
                    </span>
                  </div>

                </div>

                {/* ==================== KPI CARDS ==================== */}
                <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">

                  {/* Revenue */}
                  <div className="rounded-xl border border-white/[0.06] bg-[#11171D] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] text-slate-500">
                        Revenue
                      </span>

                      <span className="text-emerald-400">
                        ↗
                      </span>
                    </div>

                    <p className="mt-2 text-base font-semibold text-white">
                      $48.2K
                    </p>

                    <p className="mt-1 text-[9px] text-emerald-400">
                      +18.4%
                    </p>
                  </div>

                  {/* Profit */}
                  <div className="rounded-xl border border-white/[0.06] bg-[#11171D] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] text-slate-500">
                        Net Profit
                      </span>

                      <span className="text-emerald-400">
                        ↗
                      </span>
                    </div>

                    <p className="mt-2 text-base font-semibold text-white">
                      $12.7K
                    </p>

                    <p className="mt-1 text-[9px] text-emerald-400">
                      +12.8%
                    </p>
                  </div>

                  {/* Orders */}
                  <div className="rounded-xl border border-white/[0.06] bg-[#11171D] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] text-slate-500">
                        Orders
                      </span>

                      <span className="text-emerald-400">
                        ↗
                      </span>
                    </div>

                    <p className="mt-2 text-base font-semibold text-white">
                      1,284
                    </p>

                    <p className="mt-1 text-[9px] text-emerald-400">
                      +9.6%
                    </p>
                  </div>

                  {/* Margin */}
                  <div className="rounded-xl border border-white/[0.06] bg-[#11171D] p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-[9px] text-slate-500">
                        Margin
                      </span>

                      <span className="text-emerald-400">
                        ↗
                      </span>
                    </div>

                    <p className="mt-2 text-base font-semibold text-white">
                      26.3%
                    </p>

                    <p className="mt-1 text-[9px] text-emerald-400">
                      +3.2%
                    </p>
                  </div>

                </div>

                {/* ==================== CHART AREA ==================== */}
                <div className="mt-3 grid gap-3 sm:grid-cols-[1.5fr_0.8fr]">

                  {/* Revenue Chart */}
                  <div className="rounded-xl border border-white/[0.06] bg-[#11171D] p-4">

                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-[9px] text-slate-500">
                          Revenue & Profit
                        </p>

                        <p className="mt-1 text-sm font-semibold text-white">
                          $48,240
                        </p>
                      </div>

                      <div className="flex gap-3 text-[8px]">
                        <span className="flex items-center gap-1 text-slate-400">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                          Revenue
                        </span>

                        <span className="flex items-center gap-1 text-slate-400">
                          <span className="h-1.5 w-1.5 rounded-full bg-slate-500" />
                          Profit
                        </span>
                      </div>
                    </div>

                    {/* Fake Chart */}
                    <div className="relative mt-5 h-32">

                      {/* Horizontal grid */}
                      <div className="absolute inset-0 flex flex-col justify-between">
                        <span className="border-t border-white/[0.04]" />
                        <span className="border-t border-white/[0.04]" />
                        <span className="border-t border-white/[0.04]" />
                        <span className="border-t border-white/[0.04]" />
                        <span className="border-t border-white/[0.04]" />
                      </div>

                      {/* SVG Chart */}
                      <svg
                        viewBox="0 0 500 130"
                        preserveAspectRatio="none"
                        className="absolute inset-0 h-full w-full"
                      >
                        <defs>
                          <linearGradient
                            id="heroChartGradient"
                            x1="0"
                            y1="0"
                            x2="0"
                            y2="1"
                          >
                            <stop
                              offset="0%"
                              stopColor="#22C55E"
                              stopOpacity="0.25"
                            />
                            <stop
                              offset="100%"
                              stopColor="#22C55E"
                              stopOpacity="0"
                            />
                          </linearGradient>
                        </defs>

                        {/* Area */}
                        <path
                          d="M0 105 C40 100 55 85 90 90 C125 95 130 65 165 70 C205 75 210 55 245 60 C280 65 295 42 325 48 C360 55 370 30 405 38 C440 45 460 20 500 15 L500 130 L0 130 Z"
                          fill="url(#heroChartGradient)"
                        />

                        {/* Main Line */}
                        <path
                          d="M0 105 C40 100 55 85 90 90 C125 95 130 65 165 70 C205 75 210 55 245 60 C280 65 295 42 325 48 C360 55 370 30 405 38 C440 45 460 20 500 15"
                          fill="none"
                          stroke="#22C55E"
                          strokeWidth="2.5"
                          strokeLinecap="round"
                        />

                        {/* Profit Line */}
                        <path
                          d="M0 112 C45 108 60 100 95 105 C130 110 145 90 175 95 C210 100 225 82 255 88 C290 94 310 70 340 78 C375 86 390 65 420 70 C455 75 470 55 500 58"
                          fill="none"
                          stroke="#64748B"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeDasharray="5 5"
                        />

                      </svg>

                    </div>

                    {/* Chart labels */}
                    <div className="mt-2 flex justify-between text-[8px] text-slate-600">
                      <span>Jun 1</span>
                      <span>Jun 8</span>
                      <span>Jun 15</span>
                      <span>Jun 22</span>
                      <span>Jun 30</span>
                    </div>

                  </div>

                  {/* AI Insight */}
                  <div className="rounded-xl border border-emerald-400/10 bg-emerald-400/[0.035] p-4">

                    <div className="flex items-center gap-2">

                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-400">

                        <svg
                          width="15"
                          height="15"
                          viewBox="0 0 24 24"
                          fill="none"
                        >
                          <path
                            d="M12 3L13.8 8.2L19 10L13.8 11.8L12 17L10.2 11.8L5 10L10.2 8.2L12 3Z"
                            stroke="currentColor"
                            strokeWidth="1.7"
                            strokeLinejoin="round"
                          />

                          <path
                            d="M19 15L19.8 17.2L22 18L19.8 18.8L19 21L18.2 18.8L16 18L18.2 17.2L19 15Z"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinejoin="round"
                          />
                        </svg>

                      </div>

                      <span className="text-[10px] font-semibold text-emerald-300">
                        AI Insight
                      </span>

                    </div>

                    <p className="mt-4 text-[11px] font-medium leading-5 text-slate-200">
                      Your profit margin increased by 3.2% this month.
                    </p>

                    <p className="mt-2 text-[9px] leading-4 text-slate-500">
                      Revenue growth is outpacing your operating costs.
                      Consider scaling your highest-performing products.
                    </p>

                    <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/[0.05]">
                      <div className="h-full w-[78%] rounded-full bg-emerald-400" />
                    </div>

                    <p className="mt-2 text-[8px] text-slate-600">
                      Confidence score: 78%
                    </p>

                  </div>

                </div>

              </div>

            </div>

            {/* Floating Analysis Badge */}
            <div className="absolute -bottom-5 -left-5 hidden rounded-xl border border-white/[0.08] bg-[#10161C]/95 px-4 py-3 shadow-xl backdrop-blur-xl sm:block">

              <div className="flex items-center gap-3">

                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-400/10">
                  <svg
                    width="17"
                    height="17"
                    viewBox="0 0 24 24"
                    fill="none"
                    className="text-emerald-400"
                  >
                    <path
                      d="M4 19V5M4 19H20"
                      stroke="currentColor"
                      strokeWidth="1.7"
                      strokeLinecap="round"
                    />

                    <path
                      d="M7 15L10 11L13 13L18 7"
                      stroke="currentColor"
                      strokeWidth="1.7"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </div>

                <div>
                  <p className="text-[9px] text-slate-500">
                    Analysis complete
                  </p>

                  <p className="text-xs font-semibold text-white">
                    42 insights found
                  </p>
                </div>

              </div>

            </div>

          </div>

        </div>
      </div>

      {/* ==================== BOTTOM FADE ==================== */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-[#070A0D] to-transparent" />

    </section>
  );
}