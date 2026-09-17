import type { SearchResult } from "@/types/search";
import { SearchResultCard } from "@/components/SearchResultCard";

interface SearchResultsProps {
  results: SearchResult[];
}

export function SearchResults({ results }: SearchResultsProps) {
  return (
    <div className="space-y-7">
      {results.map((result, index) => (
        <SearchResultCard
          key={`${result.doc_id}-${index}`}
          result={result}
        />
      ))}
    </div>
  );
}