"use client";

import type { SearchMode } from "@/types/search";

const modes: Array<{
  value: SearchMode;
  label: string;
}> = [
  {
    value: "lexical",
    label: "Lexical",
  },
  {
    value: "semantic",
    label: "Semantic",
  },
  {
    value: "hybrid",
    label: "Hybrid",
  },
];

interface SearchModeSelectorProps {
  value: SearchMode;
  onChange: (mode: SearchMode) => void;
  disabled?: boolean;
}

export function SearchModeSelector({
  value,
  onChange,
  disabled = false,
}: SearchModeSelectorProps) {
  return (
    <div
      role="tablist"
      aria-label="Search mode"
      className="flex items-center gap-1"
    >
      {modes.map((mode) => {
        const selected = value === mode.value;

        return (
          <button
            key={mode.value}
            type="button"
            role="tab"
            aria-selected={selected}
            disabled={disabled}
            onClick={() => onChange(mode.value)}
            className={`relative px-3 py-2 text-[13px] font-medium transition-colors duration-150 ${
              selected
                ? "text-[#1a73e8]"
                : "text-[#5f6368] hover:text-[#202124]"
            } disabled:pointer-events-none disabled:opacity-50`}
          >
            {mode.label}

            {selected && (
              <span className="absolute inset-x-2 -bottom-[1px] h-[2px] rounded-full bg-[#1a73e8]" />
            )}
          </button>
        );
      })}
    </div>
  );
}