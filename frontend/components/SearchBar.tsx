"use client";

import type { FormEvent } from "react";
import type { SearchMode } from "@/types/search";
import { SearchModeSelector } from "@/components/SearchModeSelector";

interface SearchBarProps {
  query: string;
  mode: SearchMode;
  loading: boolean;
  compact?: boolean;
  onQueryChange: (query: string) => void;
  onModeChange: (mode: SearchMode) => void;
  onSubmit: () => void;
}

export function SearchBar({
  query,
  mode,
  loading,
  compact = false,
  onQueryChange,
  onModeChange,
  onSubmit,
}: SearchBarProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <div className={`w-full ${compact ? "max-w-[760px]" : "max-w-[700px]"}`}>
      <form onSubmit={handleSubmit} role="search">
        <div
          className="
            group
            flex
            h-[52px]
            items-center
            rounded-full
            border
            border-[#dfe1e5]
            bg-white
            px-4
            shadow-[0_1px_6px_rgba(32,33,36,0.10)]
            transition-all
            duration-200
            hover:border-[#d5d7da]
            hover:shadow-[0_2px_8px_rgba(32,33,36,0.14)]
            focus-within:border-[#c9d7f2]
            focus-within:shadow-[0_2px_12px_rgba(32,33,36,0.16)]
            sm:px-5
          "
        >
          <svg
            aria-hidden="true"
            className="mr-3 h-[19px] w-[19px] shrink-0 text-[#9aa0a6]"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-4-4" />
          </svg>

          <input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search the web"
            aria-label="Search query"
            autoComplete="off"
            spellCheck="false"
            className="
              min-w-0
              flex-1
              bg-transparent
              text-[16px]
              text-[#202124]
              outline-none
              placeholder:text-[#9aa0a6]
            "
          />

          {query && (
            <button
              type="button"
              aria-label="Clear search"
              onClick={() => onQueryChange("")}
              className="
                mr-2
                flex
                h-8
                w-8
                shrink-0
                items-center
                justify-center
                rounded-full
                text-[#70757a]
                transition-colors
                hover:bg-[#f1f3f4]
                hover:text-[#202124]
              "
            >
              <svg
                aria-hidden="true"
                className="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
              >
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          )}

          <button
            type="submit"
            disabled={loading || !query.trim()}
            aria-label="Submit search"
            className="
              flex
              h-9
              shrink-0
              items-center
              justify-center
              gap-2
              rounded-full
              bg-[#202124]
              px-4
              text-[13px]
              font-medium
              text-white
              transition-all
              duration-150
              hover:bg-[#3c4043]
              active:scale-[0.97]
              disabled:pointer-events-none
              disabled:opacity-35
            "
          >
            {loading ? (
              <svg
                aria-hidden="true"
                className="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  cx="12"
                  cy="12"
                  r="9"
                  className="opacity-25"
                  stroke="currentColor"
                  strokeWidth="2.5"
                />

                <path
                  d="M21 12a9 9 0 0 0-9-9"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              <>
                <span>Search</span>

                <svg
                  aria-hidden="true"
                  className="h-3.5 w-3.5"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M5 12h14" />
                  <path d="m13 6 6 6-6 6" />
                </svg>
              </>
            )}
          </button>
        </div>
      </form>

      <div
        className={`mt-2.5 flex ${
          compact ? "justify-start" : "justify-center"
        }`}
      >
        <SearchModeSelector
          value={mode}
          onChange={onModeChange}
          disabled={loading}
        />
      </div>
    </div>
  );
}