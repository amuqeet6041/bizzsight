"use client";

import { useState } from "react";
import Link from "next/link";

export default function Navbar() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // ============================================
  // CUSTOM SMOOTH SCROLL
  // ============================================
  const scrollToSection = (id) => {
    const section = document.getElementById(id);

    if (!section) {
      console.log(`Section #${id} not found`);
      return;
    }

    const navbarHeight = 80;

    const startPosition = window.scrollY;

    const sectionTop =
      section.getBoundingClientRect().top + window.scrollY;

    const targetPosition = sectionTop - navbarHeight;

    const distance = targetPosition - startPosition;

    // Animation duration
    const duration = 1000;

    let startTime = null;

    // Smooth ease-in-out animation
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

    // Close mobile menu
    setMobileMenuOpen(false);
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/[0.06] bg-[#070A0D]/85 backdrop-blur-xl">

      {/* ============================================
          NAVBAR CONTAINER
      ============================================ */}
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-6 lg:px-8">

        {/* ============================================
            LOGO
        ============================================ */}
        <Link
          href="/"
          className="group flex items-center gap-3"
          onClick={() => setMobileMenuOpen(false)}
        >
          {/* Logo Icon */}
          <div className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-400/20 bg-emerald-400/10 transition-all duration-300 group-hover:border-emerald-400/40 group-hover:bg-emerald-400/15">

            <div className="flex items-end gap-[3px]">
              <span className="h-3 w-[3px] rounded-full bg-emerald-400" />
              <span className="h-5 w-[3px] rounded-full bg-emerald-400" />
              <span className="h-7 w-[3px] rounded-full bg-emerald-300" />
              <span className="h-5 w-[3px] rounded-full bg-emerald-400" />
            </div>

          </div>

          {/* Logo Text */}
          <div className="flex flex-col">

            <span className="text-lg font-bold tracking-tight text-white">
              Biz<span className="text-emerald-400">Sight</span>
            </span>

            <span className="hidden text-[9px] font-medium uppercase tracking-[0.2em] text-slate-500 sm:block">
              Business Intelligence
            </span>

          </div>
        </Link>


        {/* ============================================
            DESKTOP NAVIGATION
        ============================================ */}
        <div className="hidden items-center gap-8 md:flex">

          

          {/* HOW IT WORKS */}
          <button
            type="button"
            onClick={() => scrollToSection("how-it-works")}
            className="cursor-pointer text-sm font-medium text-slate-400 transition-colors duration-200 hover:text-white"
          >
            How It Works
          </button>

          {/* FEATURES */}
          <button
            type="button"
            onClick={() => scrollToSection("features")}
            className="cursor-pointer text-sm font-medium text-slate-400 transition-colors duration-200 hover:text-white"
          >
            Features
          </button>

        


        </div>


        {/* ============================================
            DESKTOP ACTIONS
        ============================================ */}
        <div className="hidden items-center gap-3 md:flex">

          {/* SIGN IN */}
          <Link
            href="/login"
            className="rounded-lg px-4 py-2.5 text-sm font-medium text-slate-300 transition-all duration-200 hover:bg-white/[0.05] hover:text-white"
          >
            Sign In
          </Link>

          {/* GET STARTED */}
          <Link
            href="/analyze"
            className="group relative overflow-hidden rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-[#06100A] shadow-lg shadow-emerald-500/10 transition-all duration-300 hover:bg-emerald-400"
          >
            <span className="relative z-10 flex items-center gap-2">

              Get Started

              <svg
                width="15"
                height="15"
                viewBox="0 0 24 24"
                fill="none"
              >
                <path
                  d="M5 12H19M13 6L19 12L13 18"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>

            </span>
          </Link>

        </div>


        {/* ============================================
            MOBILE MENU BUTTON
        ============================================ */}
        <button
          type="button"
          aria-label="Toggle navigation menu"
          aria-expanded={mobileMenuOpen}
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="flex h-10 w-10 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-slate-300 transition-colors hover:bg-white/[0.06] hover:text-white md:hidden"
        >

          {mobileMenuOpen ? (

            /* CLOSE ICON */
            <svg
              width="21"
              height="21"
              viewBox="0 0 24 24"
              fill="none"
            >
              <path
                d="M6 6L18 18M6 18L18 6"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>

          ) : (

            /* MENU ICON */
            <svg
              width="21"
              height="21"
              viewBox="0 0 24 24"
              fill="none"
            >
              <path
                d="M4 7H20M4 12H20M4 17H20"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
            </svg>

          )}

        </button>

      </div>


      {/* ============================================
          MOBILE MENU
      ============================================ */}
      <div
        className={`overflow-hidden border-t border-white/[0.06] bg-[#070A0D] transition-all duration-300 md:hidden ${
          mobileMenuOpen
            ? "max-h-[500px] opacity-100"
            : "max-h-0 opacity-0"
        }`}
      >

        <div className="mx-auto max-w-7xl px-6 py-6">

          {/* MOBILE LINKS */}
          <div className="flex flex-col">

            {/* FEATURES */}
            <button
              type="button"
              onClick={() => scrollToSection("features")}
              className="cursor-pointer border-b border-white/[0.06] py-4 text-left text-sm font-medium text-slate-300 hover:text-emerald-400"
            >
              Features
            </button>

            {/* HOW IT WORKS */}
            <button
              type="button"
              onClick={() => scrollToSection("how-it-works")}
              className="cursor-pointer border-b border-white/[0.06] py-4 text-left text-sm font-medium text-slate-300 hover:text-emerald-400"
            >
              How It Works
            </button>

            {/* ANALYTICS */}
            <button
              type="button"
              onClick={() => scrollToSection("analytics")}
              className="cursor-pointer border-b border-white/[0.06] py-4 text-left text-sm font-medium text-slate-300 hover:text-emerald-400"
            >
              Analytics
            </button>

            {/* POWER BI */}
            <button
              type="button"
              onClick={() => scrollToSection("powerbi")}
              className="cursor-pointer border-b border-white/[0.06] py-4 text-left text-sm font-medium text-slate-300 hover:text-emerald-400"
            >
              Power BI
            </button>

          </div>


          {/* MOBILE ACTIONS */}
          <div className="mt-6 flex flex-col gap-3">

            {/* SIGN IN */}
            <Link
              href="/login"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center justify-center rounded-lg border border-white/[0.08] px-5 py-3 text-sm font-medium text-slate-300 hover:bg-white/[0.05] hover:text-white"
            >
              Sign In
            </Link>

            {/* GET STARTED */}
            <Link
              href="/analyze"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center justify-center gap-2 rounded-lg bg-emerald-500 px-5 py-3 text-sm font-semibold text-[#06100A] hover:bg-emerald-400"
            >
              Get Started
            </Link>

          </div>

        </div>

      </div>

    </nav>
  );
}