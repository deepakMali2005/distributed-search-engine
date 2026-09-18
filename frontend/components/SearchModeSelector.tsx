"use client";

import type { SearchMode } from "@/types/search";

const modes: Array<{
  value: SearchMode;
  label: string;
  description: string;
}> = [
  {
    value: "hybrid",
    label: "Hybrid",
    description: "Lexical + semantic",
  },
  {
    value: "semantic",
    label: "Semantic",
    description: "Meaning-based",
  },
  {
    value: "lexical",
    label: "Lexical",
    description: "Keyword-based",
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
      className="inline-flex items-center rounded-full border border-[#e3e6e8] bg-[#f5f6f7] p-1"
    >
      {modes.map((mode) => {
        const selected =
          value === mode.value;

        return (
          <button
            key={mode.value}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-label={`${mode.label}: ${mode.description}`}
            title={mode.description}
            disabled={disabled}
            onClick={() =>
              onChange(mode.value)
            }
            className={`relative rounded-full px-3.5 py-1.5 text-[12px] font-medium transition-all duration-150 sm:px-4 ${
              selected
                ? "bg-white text-[#202124] shadow-[0_1px_4px_rgba(32,33,36,0.11)]"
                : "text-[#70757a] hover:text-[#202124]"
            } disabled:pointer-events-none disabled:opacity-50`}
          >
            {mode.label}

            {selected && (
              <span
                className={`absolute bottom-0.5 left-1/2 h-0.5 w-3 -translate-x-1/2 rounded-full ${
                  mode.value === "hybrid"
                    ? "bg-[#34a853]"
                    : mode.value === "semantic"
                      ? "bg-[#7e57c2]"
                      : "bg-[#1a73e8]"
                }`}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}