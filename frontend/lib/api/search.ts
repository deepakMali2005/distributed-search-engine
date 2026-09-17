import type {
  SearchMode,
  SearchResponse,
} from "@/types/search";

interface SearchOptions {
  query: string;
  mode: SearchMode;
  limit?: number;
}

export async function searchDocuments({
  query,
  mode,
  limit = 10,
}: SearchOptions): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    mode,
    limit: String(limit),
  });

  const response = await fetch(
    `/api/search?${params.toString()}`,
    {
      method: "GET",
      cache: "no-store",
    },
  );

  const body = await response
    .json()
    .catch(() => null);

  if (!response.ok) {
    const detail =
      body &&
      typeof body.detail === "string"
        ? body.detail
        : "Search service is currently unavailable.";

    throw new Error(detail);
  }

  return body as SearchResponse;
}