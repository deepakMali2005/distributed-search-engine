import type { SearchResponse } from "@/types/search";

interface SearchMetadataProps {
  response: SearchResponse;
}

function formatMode(mode: SearchResponse["mode"]): string {
  return mode.charAt(0).toUpperCase() + mode.slice(1);
}

export function SearchMetadata({
  response,
}: SearchMetadataProps) {
  const resultCount = response.results.length;

  const shardStatus = response.partial
    ? `${response.successful_shards}/${response.total_shards} shards`
    : `${response.total_shards} shards`;

  return (
    <div className="mb-7 flex flex-wrap items-center gap-x-2.5 gap-y-2 text-[12px] text-[#80868b]">
      <span>
        {resultCount} {resultCount === 1 ? "result" : "results"}
      </span>

      <span
        aria-hidden="true"
        className="text-[#c7c9cc]"
      >
        •
      </span>

      <span>{formatMode(response.mode)}</span>

      <span
        aria-hidden="true"
        className="text-[#c7c9cc]"
      >
        •
      </span>

      <span>{shardStatus}</span>

      {response.failed_shards > 0 && (
        <>
          <span
            aria-hidden="true"
            className="text-[#c7c9cc]"
          >
            •
          </span>

          <span className="text-[#b3261e]">
            {response.failed_shards} failed
          </span>
        </>
      )}

      {response.timed_out_shards > 0 && (
        <>
          <span
            aria-hidden="true"
            className="text-[#c7c9cc]"
          >
            •
          </span>

          <span className="text-[#b3261e]">
            {response.timed_out_shards} timed out
          </span>
        </>
      )}

      {response.partial && (
        <span
          className="
            ml-1
            rounded-full
            border
            border-[#f1dfad]
            bg-[#fff9e8]
            px-2
            py-0.5
            text-[11px]
            font-medium
            text-[#8a6200]
          "
        >
          Partial
        </span>
      )}
    </div>
  );
}