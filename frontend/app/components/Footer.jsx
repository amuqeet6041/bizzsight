
export default function Footer() {
  return (
    <footer className="border-t border-white/10 bg-[#070A0D]">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 px-6 py-8 sm:flex-row">

        {/* BizSight Logo & Name */}
        <div className="flex items-center gap-3">
          {/* Logo */}
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-emerald-400/30 bg-emerald-400/10">
            <span className="text-lg font-bold text-emerald-400">
              B
            </span>
          </div>

          {/* Name */}
          <div>
            <h2 className="text-lg font-bold tracking-wide text-white">
              Biz<span className="text-emerald-400">Sight</span>
            </h2>

            <p className="text-xs text-gray-500">
              SME Business Intelligence
            </p>
          </div>
        </div>

        {/* Developer Credit */}
        <div className="flex items-center gap-2 text-sm text-gray-400">
          <span>Developed by</span>

          <a
            href="https://github.com/amuqeet6041"
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-center gap-2 font-medium text-white transition-colors hover:text-emerald-400"
            aria-label="Abdul Muqeet GitHub Profile"
          >
            {/* GitHub Logo */}
            <svg
              viewBox="0 0 24 24"
              className="h-5 w-5 fill-current transition-transform group-hover:scale-110"
              aria-hidden="true"
            >
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.3 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.725-4.042-1.61-4.042-1.61-.546-1.385-1.333-1.754-1.333-1.754-1.09-.745.083-.73.083-.73 1.205.085 1.84 1.237 1.84 1.237 1.07 1.835 2.807 1.305 3.492.998.108-.776.418-1.305.762-1.605-2.665-.303-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.125-.303-.535-1.523.115-3.175 0 0 1.005-.322 3.3 1.23.96-.267 1.985-.4 3.005-.405 1.02.005 2.045.138 3.005.405 2.295-1.552 3.3-1.23 3.3-1.23.65 1.652.24 2.872.115 3.175.77.84 1.235 1.91 1.235 3.22 0 4.61-2.805 5.625-5.475 5.922.43.372.815 1.103.815 2.222 0 1.606-.015 2.896-.015 3.286 0 .322.215.695.825.577C20.565 21.795 24 17.295 24 12c0-6.63-5.37-12-12-12z" />
            </svg>

            <span>Abdul Muqeet</span>
          </a>
        </div>

      </div>
    </footer>
  );
}

