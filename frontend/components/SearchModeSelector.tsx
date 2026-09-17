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
    <div className="inline-flex rounded-full border border-zinc-200 bg-white p-1 shadow-sm">
      {modes.map((mode) => {
        const selected = value === mode.value;

        return (
          <button
            key={mode.value}
            type="button"
            disabled={disabled}
            aria-pressed={selected}
            onClick={() => onChange(mode.value)}
            className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${
              selected
                ? "bg-zinc-900 text-white"
                : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            {mode.label}
          </button>
        );
      })}
    </div>
  );
}