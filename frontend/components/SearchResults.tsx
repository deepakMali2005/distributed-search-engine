import type { SearchResult } from "@/types/search";
import { SearchResultCard } from "@/components/SearchResultCard";

interface SearchResultsProps {
  results: SearchResult[];
}

export function SearchResults({
  results,
}: SearchResultsProps) {
  return (
    <div className="space-y-9">
      {results.map((result) => (
        <SearchResultCard
          key={result.doc_id}
          result={result}
        />
      ))}
    </div>
  );
}