import type { SearchResponse } from "@/types/search";

interface SearchMetadataProps {
  response: SearchResponse;
}

function formatMode(
  mode: SearchResponse["mode"]
): string {
  return (
    mode.charAt(0).toUpperCase() +
    mode.slice(1)
  );
}

export function SearchMetadata({
  response,
}: SearchMetadataProps) {
  const resultCount =
    response.results.length;

  const shardStatus = response.partial
    ? `${response.successful_shards}/${response.total_shards} shards`
    : `${response.total_shards} shards`;

  return (
    <div className="mb-8 flex flex-wrap items-center gap-x-2 gap-y-2 text-[12px] text-[#80868b]">
      <span>
        {resultCount}{" "}
        {resultCount === 1
          ? "result"
          : "results"}
      </span>

      <span aria-hidden="true">
        ·
      </span>

      <span>
        {formatMode(response.mode)} search
      </span>

      <span aria-hidden="true">
        ·
      </span>

      <span>{shardStatus}</span>

      {response.partial && (
        <span className="ml-1 inline-flex items-center gap-1.5 rounded-full border border-[#f1dfad] bg-[#fff9e8] px-2.5 py-1 text-[11px] font-medium text-[#8a6200]">
          <span className="h-1.5 w-1.5 rounded-full bg-[#d99b00]" />
          Partial results
        </span>
      )}

      {response.failed_shards > 0 && (
        <span className="rounded-full bg-[#fff3f3] px-2 py-1 text-[11px] font-medium text-[#b3261e]">
          {response.failed_shards} failed
        </span>
      )}

      {response.timed_out_shards > 0 && (
        <span className="rounded-full bg-[#fff3f3] px-2 py-1 text-[11px] font-medium text-[#b3261e]">
          {response.timed_out_shards} timed out
        </span>
      )}
    </div>
  );
}