import type { SearchResult } from "@/types/search";
import { SearchResultCard } from "@/components/SearchResultCard";

interface SearchResultsProps {
  results: SearchResult[];
  query: string;
}

export function SearchResults({
  results,
  query,
}: SearchResultsProps) {
  return (
    <div className="space-y-8">
      {results.map((result, index) => (
        <SearchResultCard
          key={`${result.doc_id}-${index}`}
          result={result}
          query={query}
        />
      ))}
    </div>
  );
}