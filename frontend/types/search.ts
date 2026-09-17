export type SearchMode = "lexical" | "semantic" | "hybrid";

export interface SearchResult {
  doc_id: number;
  title?: string | null;
  url?: string | null;
  snippet?: string | null;
  score: number;
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  results: SearchResult[];
  total_shards: number;
  successful_shards: number;
  failed_shards: number;
  timed_out_shards: number;
  partial: boolean;
}