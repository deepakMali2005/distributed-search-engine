import type { SearchResult } from "@/types/search";

interface SearchResultCardProps {
  result: SearchResult;
}

function displayUrl(url: string): string {
  try {
    const parsed = new URL(url);

    const path =
      parsed.pathname === "/"
        ? ""
        : parsed.pathname;

    return `${parsed.host}${path}`;
  } catch {
    return url;
  }
}

export function SearchResultCard({
  result,
}: SearchResultCardProps) {
  const title =
    result.title?.trim() ||
    result.url ||
    `Document ${result.doc_id}`;

  const url = result.url;

  return (
    <article className="group max-w-3xl">
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="block"
        >
          <p
            className="mb-1 truncate text-sm text-emerald-700"
            title={url}
          >
            {displayUrl(url)}
          </p>

          <h2 className="text-xl font-medium leading-7 text-blue-700 group-hover:underline">
            {title}
          </h2>
        </a>
      ) : (
        <h2 className="text-xl font-medium leading-7 text-zinc-900">
          {title}
        </h2>
      )}

      {result.snippet && (
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          {result.snippet}
        </p>
      )}
    </article>
  );
}