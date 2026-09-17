"use client";

import { useState } from "react";
import { SearchBar } from "@/components/SearchBar";
import { SearchMetadata } from "@/components/SearchMetadata";
import { SearchResults } from "@/components/SearchResults";
import { searchDocuments } from "@/lib/api/search";
import type { SearchMode, SearchResponse } from "@/types/search";

export default function Home() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<SearchMode>("hybrid");
  const [response, setResponse] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const hasSearched = response !== null || error !== null;

  return (
    <main className="min-h-screen bg-white text-zinc-900">
      <div className="mx-auto min-h-screen max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
        <header
          className={`transition-all ${
            hasSearched
              ? "mb-10"
              : "flex min-h-[70vh] flex-col justify-center"
          }`}
        >
          <div className="mb-8">
            <p className="text-sm font-semibold uppercase tracking-[0.22em] text-zinc-500">
              Distributed Search
            </p>

            {!hasSearched && (
              <>
                <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
                  Search the web you crawled.
                </h1>

                <p className="mt-4 max-w-2xl text-base leading-7 text-zinc-500 sm:text-lg">
                  Lexical, semantic, and hybrid retrieval powered by a
                  distributed search engine.
                </p>
              </>
            )}
          </div>

          <SearchBar
            query={query}
            mode={mode}
            loading={loading}
            onQueryChange={setQuery}
            onModeChange={setMode}
            onSubmit={handleSearch}
          />
        </header>

        {loading && (
          <div className="max-w-3xl py-8 text-sm text-zinc-500">
            Searching the distributed index...
          </div>
        )}

        {!loading && error && (
          <div
            role="alert"
            className="max-w-3xl rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
          >
            {error}
          </div>
        )}

        {!loading && response && (
          <section aria-label="Search results" className="pb-16">
            <SearchMetadata response={response} />

            {response.results.length === 0 ? (
              <div className="max-w-3xl py-8">
                <h2 className="text-lg font-medium text-zinc-900">
                  No results found
                </h2>

                <p className="mt-2 text-sm text-zinc-500">
                  No documents matched &quot;{response.query}&quot;.
                </p>
              </div>
            ) : (
              <SearchResults results={response.results} />
            )}
          </section>
        )}
      </div>
    </main>
  );
}