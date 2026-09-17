import type { SearchResponse } from "@/types/search";

interface SearchMetadataProps {
  response: SearchResponse;
}

export function SearchMetadata({
  response,
}: SearchMetadataProps) {
  const shardStatus = response.partial
    ? `${response.successful_shards} of ${response.total_shards} shards`
    : `${response.total_shards} shards`;

  return (
    <div className="mb-8 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-zinc-500">
      <span className="font-medium capitalize text-zinc-700">
        {response.mode} search
      </span>

      <span>
        {response.results.length}{" "}
        {response.results.length === 1 ? "result" : "results"}
      </span>

      <span>{shardStatus}</span>

      {response.failed_shards > 0 && (
        <span>
          {response.failed_shards} failed
        </span>
      )}

      {response.timed_out_shards > 0 && (
        <span>
          {response.timed_out_shards} timed out
        </span>
      )}

      {response.partial && (
        <span className="font-medium text-amber-700">
          Partial results
        </span>
      )}
    </div>
  );
}