"use client";

import type { FormEvent } from "react";
import type { SearchMode } from "@/types/search";
import { SearchModeSelector } from "@/components/SearchModeSelector";

interface SearchBarProps {
  query: string;
  mode: SearchMode;
  loading: boolean;
  onQueryChange: (query: string) => void;
  onModeChange: (mode: SearchMode) => void;
  onSubmit: () => void;
}

export function SearchBar({
  query,
  mode,
  loading,
  onQueryChange,
  onModeChange,
  onSubmit,
}: SearchBarProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <div className="w-full max-w-3xl">
      <form onSubmit={handleSubmit}>
        <div className="flex items-center rounded-full border border-zinc-300 bg-white px-5 py-2 shadow-sm transition-shadow focus-within:shadow-md">
          <svg
            aria-hidden="true"
            className="mr-3 h-5 w-5 shrink-0 text-zinc-400"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-4-4" />
          </svg>

          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search the distributed index"
            aria-label="Search query"
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent py-2 text-base text-zinc-900 outline-none placeholder:text-zinc-400"
          />

          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => onQueryChange("")}
              className="mr-2 rounded-full p-1 text-zinc-400 transition-colors hover:bg-zinc-100 hover:text-zinc-700"
            >
              <svg
                aria-hidden="true"
                className="h-5 w-5"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          )}

          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="rounded-full bg-zinc-900 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      <div className="mt-4 flex justify-center sm:justify-start">
        <SearchModeSelector
          value={mode}
          onChange={onModeChange}
          disabled={loading}
        />
      </div>
    </div>
  );
}