"use client";

import { useState } from "react";
import { SearchBar } from "@/components/SearchBar";
import { SearchMetadata } from "@/components/SearchMetadata";
import { SearchResults } from "@/components/SearchResults";
import { StrataLogo } from "@/components/StrataLogo";
import { searchDocuments } from "@/lib/api/search";
import type { SearchMode, SearchResponse } from "@/types/search";

const suggestions = [
  "distributed systems",
  "how does semantic search work",
  "vector embeddings",
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (nextQuery = query) => {
    const trimmedQuery = nextQuery.trim();

    if (!trimmedQuery) {
      setResponse(null);
      setError(null);
      return;
    }

    setQuery(trimmedQuery);
    setLoading(true);
    setError(null);

    try {
      const result = await searchDocuments({
        query: trimmedQuery,
        mode,
        limit: 10,
      });

      setResponse(result);
    } catch {
      setResponse(null);
      setError(
        "Search service is currently unavailable. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const hasSearched = response !== null || error !== null;

  return (
    <main className="min-h-screen bg-[#fbfcfe] text-[#202124]">
      <div
        className={`mx-auto w-full px-5 sm:px-8 ${
          hasSearched ? "max-w-305" : "max-w-5xl"
        }`}
      >
        <header
          className={
            hasSearched
              ? "border-b border-[#edf0f2] py-5"
              : "flex min-h-[72vh] flex-col justify-center pb-16 pt-10"
          }
        >
          <div
            className={
              hasSearched
                ? "flex flex-col gap-5 lg:flex-row lg:items-center"
                : "flex flex-col items-center"
            }
          >
            <a
              href="/"
              aria-label="STRATA home"
              className={`group shrink-0 select-none ${
                hasSearched
                  ? "self-start lg:self-auto"
                  : "mb-9"
              }`}
            >
              <StrataLogo compact={hasSearched} />
            </a>

            <SearchBar
              query={query}
              mode={mode}
              loading={loading}
              compact={hasSearched}
              onQueryChange={setQuery}
              onModeChange={setMode}
              onSubmit={handleSearch}
            />
          </div>

          {!hasSearched && (
            <div className="mt-10 text-center">
              <div className="mx-auto mb-5 inline-flex items-center gap-2 rounded-full border border-[#e4e7eb] bg-white px-3.5 py-1.5 text-[11px] font-medium text-[#5f6368] shadow-[0_1px_3px_rgba(32,33,36,0.04)]">
                <span className="relative flex h-2 w-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#34a853] opacity-50" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-[#34a853]" />
                </span>

                Distributed index online
              </div>

              <h1 className="mx-auto max-w-3xl text-4xl font-semibold tracking-[-0.06em] text-[#202124] sm:text-[58px] sm:leading-[1.02]">
                Search by words.
                <br />
                <span className="text-[#5f6368]">
                  Search by meaning.
                </span>
              </h1>

              <p className="mx-auto mt-5 max-w-xl text-[15px] leading-7 text-[#70757a] sm:text-base">
                STRATA combines lexical matching and semantic understanding
                across a distributed search index.
              </p>

              <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => handleSearch(suggestion)}
                    className="rounded-full border border-[#e1e5e9] bg-white px-3.5 py-2 text-[12px] text-[#5f6368] shadow-[0_1px_3px_rgba(32,33,36,0.03)] transition duration-150 hover:-translate-y-0.5 hover:border-[#cfd4da] hover:text-[#202124] hover:shadow-[0_4px_10px_rgba(32,33,36,0.07)]"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>

              <div className="mt-10 flex items-center justify-center gap-5 text-[11px] text-[#9aa0a6]">
                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#1a73e8]" />
                  Lexical
                </span>

                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#7e57c2]" />
                  Semantic
                </span>

                <span className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#34a853]" />
                  Hybrid
                </span>
              </div>
            </div>
          )}
        </header>

        <div className={hasSearched ? "mx-auto max-w-195" : ""}>
          {loading && (
            <div
              className="py-10"
              role="status"
              aria-live="polite"
            >
              <div className="mb-5 h-0.5 overflow-hidden rounded-full bg-[#edf0f2]">
                <div className="h-full w-1/3 animate-search-progress rounded-full bg-[#1a73e8]" />
              </div>

              <div className="flex items-center gap-2 text-[13px] text-[#70757a]">
                <svg
                  aria-hidden="true"
                  className="h-3.5 w-3.5 animate-spin"
                  viewBox="0 0 24 24"
                  fill="none"
                >
                  <circle
                    cx="12"
                    cy="12"
                    r="9"
                    stroke="currentColor"
                    strokeWidth="2"
                    className="opacity-20"
                  />

                  <path
                    d="M21 12a9 9 0 0 0-9-9"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>

                Searching across the distributed index…
              </div>
            </div>
          )}

          {!loading && error && (
            <div
              role="alert"
              className="my-8 flex items-start gap-3 rounded-2xl border border-[#f1c4c4] bg-[#fff8f8] px-5 py-4 text-sm text-[#b3261e]"
            >
              <svg
                aria-hidden="true"
                className="mt-0.5 h-4 w-4 shrink-0"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="9" />
                <path d="M12 8v5" />
                <path d="M12 16h.01" />
              </svg>

              <span>{error}</span>
            </div>
          )}

          {!loading && response && (
            <section
              aria-label="Search results"
              className="pb-20 pt-7 sm:pt-9"
            >
              <SearchMetadata response={response} />

              {response.results.length === 0 ? (
                <div className="rounded-2xl border border-[#e7eaed] bg-white px-6 py-10 shadow-[0_1px_4px_rgba(32,33,36,0.04)]">
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-[#f1f3f4] text-[#5f6368]">
                    <svg
                      aria-hidden="true"
                      className="h-5 w-5"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.8"
                    >
                      <circle cx="11" cy="11" r="7" />
                      <path d="m20 20-4-4" />
                      <path d="M8.5 8.5 13.5 13.5" />
                      <path d="m13.5 8.5-5 5" />
                    </svg>
                  </div>

                  <h2 className="text-xl font-semibold tracking-tight">
                    No results found
                  </h2>

                  <p className="mt-2 max-w-xl text-sm leading-6 text-[#70757a]">
                    STRATA couldn&apos;t find pages matching{" "}
                    <span className="font-medium text-[#4d5156]">
                      &quot;{response.query}&quot;
                    </span>
                    .
                  </p>

                  <p className="mt-1 text-sm text-[#80868b]">
                    Try broader wording or switch between Hybrid, Semantic,
                    and Lexical search.
                  </p>
                </div>
              ) : (
                <SearchResults
                  results={response.results}
                  query={response.query}
                />
              )}
            </section>
          )}
        </div>
      </div>

      <footer className="border-t border-[#edf0f2] py-7 text-center">
        <div className="flex items-center justify-center gap-2 text-[11px] text-[#9aa0a6]">
          <span className="font-semibold tracking-[0.12em] text-[#70757a]">
            STRATA
          </span>

          <span>·</span>

          <span>Distributed Hybrid Search</span>
        </div>
      </footer>
    </main>
  );
}