import type { SearchResult } from "@/types/search";

interface SearchResultCardProps {
  result: SearchResult;
}

interface UrlParts {
  domain: string;
  path: string;
}

function getUrlParts(url: string): UrlParts {
  try {
    const parsed = new URL(url);

    return {
      domain: parsed.hostname.replace(/^www\./, ""),
      path: parsed.pathname === "/" ? "" : parsed.pathname,
    };
  } catch {
    return {
      domain: url,
      path: "",
    };
  }
}

function humanizeSegment(segment: string): string {
  return decodeURIComponent(segment)
    .replace(/\.[a-z0-9]+$/i, "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function titleFromUrl(url: string): string | null {
  try {
    const parsed = new URL(url);

    const segments = parsed.pathname
      .split("/")
      .filter(Boolean);

    const lastSegment = segments.at(-1);

    if (lastSegment) {
      const readable = humanizeSegment(lastSegment);

      if (readable) {
        return readable;
      }
    }

    const hostname = parsed.hostname
      .replace(/^www\./, "")
      .split(".")[0];

    if (hostname) {
      return humanizeSegment(hostname);
    }

    return null;
  } catch {
    return null;
  }
}

function titleFromSnippet(
  snippet: string | null | undefined,
): string | null {
  const cleaned = snippet
    ?.replace(/\s+/g, " ")
    .trim();

  if (!cleaned) {
    return null;
  }

  const firstSentence = cleaned.split(/[.!?]\s/)[0]?.trim();

  if (!firstSentence) {
    return null;
  }

  if (firstSentence.length <= 80) {
    return firstSentence;
  }

  return `${firstSentence.slice(0, 77).trimEnd()}...`;
}

function getDisplayTitle(result: SearchResult): string {
  const title = result.title?.trim();

  if (title) {
    return title;
  }

  if (result.url?.trim()) {
    const urlTitle = titleFromUrl(result.url.trim());

    if (urlTitle) {
      return urlTitle;
    }
  }

  const snippetTitle = titleFromSnippet(result.snippet);

  if (snippetTitle) {
    return snippetTitle;
  }

  return "Search result";
}

function getInitial(domain: string): string {
  const firstCharacter = domain
    .replace(/[^a-zA-Z0-9]/g, "")
    .charAt(0);

  return firstCharacter
    ? firstCharacter.toUpperCase()
    : "W";
}

export function SearchResultCard({
  result,
}: SearchResultCardProps) {
  const title = getDisplayTitle(result);

  const url = result.url?.trim() || null;

  const urlParts = url
    ? getUrlParts(url)
    : null;

  const domain = urlParts?.domain || null;

  return (
    <article
      className="
        group
        border-b
        border-[#f1f3f4]
        pb-7
        last:border-b-0
        sm:pb-8
      "
    >
      {url && urlParts ? (
        <>
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="
              block
              rounded-lg
              outline-none
              focus-visible:ring-2
              focus-visible:ring-[#8ab4f8]
            "
          >
            <div className="mb-1.5 flex min-w-0 items-center gap-2">
              <span
                aria-hidden="true"
                className="
                  flex
                  h-6
                  w-6
                  shrink-0
                  items-center
                  justify-center
                  rounded-full
                  border
                  border-[#e5e7eb]
                  bg-white
                  text-[10px]
                  font-semibold
                  text-[#5f6368]
                  shadow-[0_1px_2px_rgba(0,0,0,0.05)]
                "
              >
                {getInitial(urlParts.domain)}
              </span>

              <div className="min-w-0">
                <div className="truncate text-[13px] font-medium leading-5 text-[#3c4043]">
                  {domain}
                </div>

                {urlParts.path && (
                  <div className="hidden truncate text-[12px] leading-4 text-[#80868b] sm:block">
                    {urlParts.path}
                  </div>
                )}
              </div>
            </div>

            <h2
              className="
                max-w-[720px]
                text-[20px]
                font-normal
                leading-[1.35]
                tracking-[-0.012em]
                text-[#1a0dab]
                transition-colors
                group-hover:text-[#1558b0]
                group-hover:underline
                group-focus-visible:underline
                sm:text-[21px]
              "
            >
              {title}
            </h2>
          </a>
        </>
      ) : (
        <h2
          className="
            max-w-[720px]
            text-[20px]
            font-normal
            leading-[1.35]
            tracking-[-0.012em]
            text-[#202124]
            sm:text-[21px]
          "
        >
          {title}
        </h2>
      )}

      {result.snippet?.trim() && (
        <p
          className="
            mt-2
            max-w-[720px]
            text-[14px]
            leading-[1.65]
            text-[#4d5156]
            sm:text-[15px]
          "
        >
          {result.snippet.trim()}
        </p>
      )}
    </article>
  );
}