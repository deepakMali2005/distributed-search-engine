"use client";

import { useState } from "react";
import { SearchBar } from "@/components/SearchBar";
import { SearchMetadata } from "@/components/SearchMetadata";
import { SearchResults } from "@/components/SearchResults";
import { searchDocuments } from "@/lib/api/search";
import type {
  SearchMode,
  SearchResponse,
} from "@/types/search";

export default function Home() {
  const [query, setQuery] = useState("");
  const [mode, setMode] =
    useState<SearchMode>("hybrid");

  const [response, setResponse] =
    useState<SearchResponse | null>(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);

  const handleSearch = async () => {
    const trimmedQuery = query.trim();

    if (!trimmedQuery) {
      setResponse(null);
      setError(null);
      return;
    }

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
        "Search service is currently unavailable. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  const hasSearched =
    response !== null || error !== null;

  return (
    <main className="min-h-screen bg-white text-[#202124]">
      <div
        className={`mx-auto w-full px-5 sm:px-8 ${
          hasSearched
            ? "max-w-[1180px]"
            : "max-w-5xl"
        }`}
      >
        <header
          className={
            hasSearched
              ? "border-b border-[#f1f3f4] py-5"
              : "flex min-h-[67vh] flex-col justify-center pb-16 pt-10"
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
              aria-label="Distributed Search home"
              className={`group shrink-0 select-none ${
                hasSearched
                  ? "self-start lg:self-auto"
                  : "mb-8"
              }`}
            >
              <div className="flex items-baseline">
                <span
                  className="
                    text-[25px]
                    font-semibold
                    tracking-[-0.045em]
                    text-[#202124]
                  "
                >
                  distributed
                </span>

                <span
                  className="
                    ml-1
                    text-[25px]
                    font-semibold
                    tracking-[-0.045em]
                    text-[#1a73e8]
                  "
                >
                  search
                </span>
              </div>

              {!hasSearched && (
                <div
                  className="
                    mt-1
                    text-center
                    text-[11px]
                    font-medium
                    uppercase
                    tracking-[0.18em]
                    text-[#9aa0a6]
                  "
                >
                  distributed web search
                </div>
              )}
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
            <div className="mt-9 text-center">
              <h1
                className="
                  mx-auto
                  max-w-2xl
                  text-3xl
                  font-semibold
                  tracking-[-0.04em]
                  text-[#202124]
                  sm:text-[40px]
                "
              >
                Search the distributed web.
              </h1>

              <p
                className="
                  mx-auto
                  mt-3
                  max-w-xl
                  text-[15px]
                  leading-7
                  text-[#70757a]
                  sm:text-base
                "
              >
                Find relevant pages using lexical,
                semantic, or hybrid search across
                a distributed index.
              </p>

              <div
                className="
                  mt-6
                  flex
                  items-center
                  justify-center
                  gap-2
                  text-xs
                  text-[#9aa0a6]
                "
              >
                <span
                  className="
                    h-1.5
                    w-1.5
                    rounded-full
                    bg-[#34a853]
                  "
                />

                <span>
                  Distributed index online
                </span>
              </div>
            </div>
          )}
        </header>

        <div
          className={
            hasSearched
              ? "mx-auto max-w-[760px]"
              : ""
          }
        >
          {loading && (
            <div
              className="py-10"
              role="status"
              aria-live="polite"
            >
              <div
                className="
                  mb-4
                  h-[2px]
                  overflow-hidden
                  rounded-full
                  bg-[#f1f3f4]
                "
              >
                <div
                  className="
                    h-full
                    w-1/3
                    animate-search-progress
                    rounded-full
                    bg-[#1a73e8]
                  "
                />
              </div>

              <div
                className="
                  flex
                  items-center
                  gap-2
                  text-[13px]
                  text-[#70757a]
                "
              >
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

                <span>
                  Searching the distributed index…
                </span>
              </div>
            </div>
          )}

          {!loading && error && (
            <div
              role="alert"
              className="
                my-8
                rounded-xl
                border
                border-[#f1c4c4]
                bg-[#fff8f8]
                px-5
                py-4
                text-sm
                text-[#b3261e]
              "
            >
              {error}
            </div>
          )}

          {!loading && response && (
            <section
              aria-label="Search results"
              className="
                pb-20
                pt-6
                sm:pt-8
              "
            >
              <SearchMetadata
                response={response}
              />

              {response.results.length === 0 ? (
                <div className="py-10">
                  <div
                    className="
                      mb-5
                      flex
                      h-12
                      w-12
                      items-center
                      justify-center
                      rounded-full
                      border
                      border-[#e8eaed]
                      bg-[#f8f9fa]
                      text-[#70757a]
                    "
                  >
                    <svg
                      aria-hidden="true"
                      className="h-5 w-5"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.7"
                    >
                      <circle
                        cx="11"
                        cy="11"
                        r="7"
                      />

                      <path d="m20 20-4-4" />
                    </svg>
                  </div>

                  <h2
                    className="
                      text-xl
                      font-medium
                      tracking-[-0.02em]
                      text-[#202124]
                    "
                  >
                    No results found
                  </h2>

                  <p
                    className="
                      mt-2
                      max-w-xl
                      text-sm
                      leading-6
                      text-[#70757a]
                    "
                  >
                    We couldn&apos;t find pages
                    matching{" "}
                    <span className="font-medium text-[#4d5156]">
                      &quot;{response.query}&quot;
                    </span>
                    . Try different words or a
                    broader query.
                  </p>
                </div>
              ) : (
                <SearchResults
                  results={response.results}
                />
              )}
            </section>
          )}
        </div>
      </div>

      <footer
        className="
          border-t
          border-[#f5f5f5]
          py-5
          text-center
          text-[11px]
          text-[#9aa0a6]
        "
      >
        Distributed Search Engine
      </footer>
    </main>
  );
}