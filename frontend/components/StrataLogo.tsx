interface StrataLogoProps {
  compact?: boolean;
}

export function StrataLogo({
  compact = false,
}: StrataLogoProps) {
  return (
    <span
      className="inline-flex items-center gap-2.5"
      aria-hidden="true"
    >
      <span className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[#d9dce1] bg-white shadow-[0_2px_8px_rgba(32,33,36,0.08)] transition-transform duration-200 group-hover:scale-[1.03]">
        <svg
          viewBox="0 0 36 36"
          className="h-7 w-7"
          fill="none"
        >
          <path
            d="M7 10.5 18 6l11 4.5-11 4.5-11-4.5Z"
            fill="currentColor"
            className="text-[#202124]"
          />

          <path
            d="m7 15.5 11 4.5 11-4.5v4L18 24l-11-4.5v-4Z"
            fill="currentColor"
            className="text-[#5f6368]"
          />

          <path
            d="m7 23 11 4.5L29 23v4L18 31.5 7 27v-4Z"
            fill="currentColor"
            className="text-[#9aa0a6]"
          />

          <circle
            cx="28.5"
            cy="27.5"
            r="3.5"
            fill="white"
          />

          <circle
            cx="28.5"
            cy="27.5"
            r="2"
            fill="#1a73e8"
          />
        </svg>
      </span>

      <span className="flex flex-col leading-none">
        <span className="text-[22px] font-bold tracking-[-0.055em] text-[#202124]">
          STRATA
        </span>

        {!compact && (
          <span className="mt-1 text-[8px] font-semibold uppercase tracking-[0.18em] text-[#80868b]">
            Distributed Search
          </span>
        )}
      </span>
    </span>
  );
}