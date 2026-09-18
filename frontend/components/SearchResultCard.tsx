"use client";

import { useState } from "react";
import type { SearchResult } from "@/types/search";

interface SearchResultCardProps {
  result: SearchResult;
  query: string;
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

function getInitial(domain: string): string {
  const firstCharacter = domain
    .replace(/[^a-zA-Z0-9]/g, "")
    .charAt(0);

  return firstCharacter
    ? firstCharacter.toUpperCase()
    : "W";
}

function getDisplayTitle(result: SearchResult): string {
  const title = result.title?.trim();

  if (title) {
    return title;
  }

  try {
    const parsed = new URL(result.url || "");

    const segment = parsed.pathname
      .split("/")
      .filter(Boolean)
      .at(-1);

    if (segment) {
      const readable = decodeURIComponent(segment)
        .replace(/\.[a-z0-9]+$/i, "")
        .replace(/[-_]+/g, " ")
        .replace(/\s+/g, " ")
        .trim();

      if (readable) {
        return readable.replace(
          /\b\w/g,
          (letter) => letter.toUpperCase()
        );
      }
    }

    return parsed.hostname.replace(/^www\./, "");
  } catch {
    return "Search result";
  }
}

function getFaviconUrl(url: string): string | null {
  try {
    return `${new URL(url).origin}/favicon.ico`;
  } catch {
    return null;
  }
}

function getSearchTerms(query: string): string[] {
  return query
    .toLowerCase()
    .split(/\s+/)
    .map((term) => term.trim())
    .filter((term) => term.length > 1)
    .filter(
      (term, index, array) =>
        array.indexOf(term) === index
    );
}

function HighlightedText({
  text,
  query,
}: {
  text: string;
  query: string;
}) {
  const terms = getSearchTerms(query);

  if (!text || terms.length === 0) {
    return <>{text}</>;
  }

  const escapedTerms = terms.map((term) =>
    term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
  );

  const regex = new RegExp(
    `(${escapedTerms.join("|")})`,
    "gi"
  );

  const parts = text.split(regex);

  return (
    <>
      {parts.map((part, index) => {
        const isMatch = terms.some(
          (term) =>
            part.toLowerCase() === term.toLowerCase()
        );

        if (!isMatch) {
          return (
            <span key={index}>
              {part}
            </span>
          );
        }

        return (
          <mark
            key={index}
            className="rounded-[3px] bg-[#fff1a8] px-px text-inherit"
          >
            {part}
          </mark>
        );
      })}
    </>
  );
}

export function SearchResultCard({
  result,
  query,
}: SearchResultCardProps) {
  const [faviconFailed, setFaviconFailed] =
    useState(false);

  const url = result.url?.trim() || null;

  const urlParts = url
    ? getUrlParts(url)
    : null;

  const domain = urlParts?.domain || null;

  const title = getDisplayTitle(result);

  const favicon =
    url && !faviconFailed
      ? getFaviconUrl(url)
      : null;

  return (
    <article className="group border-b border-[#edf0f2] pb-8 last:border-b-0">
      {url && urlParts ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="block rounded-xl outline-none focus-visible:ring-2 focus-visible:ring-[#8ab4f8] focus-visible:ring-offset-4"
        >
          <div className="mb-2.5 flex min-w-0 items-center gap-2.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center overflow-hidden rounded-[10px] border border-[#e3e6e8] bg-white text-[10px] font-semibold text-[#5f6368] shadow-[0_1px_3px_rgba(32,33,36,0.06)]">
              {favicon ? (
                <img
                  src={favicon}
                  alt=""
                  className="h-4 w-4 object-contain"
                  onError={() => setFaviconFailed(true)}
                />
              ) : (
                getInitial(domain || "web")
              )}
            </span>

            <div className="min-w-0 leading-tight">
              <div className="truncate text-[13px] font-medium text-[#3c4043]">
                {domain}
              </div>

              {urlParts.path && (
                <div className="mt-0.5 truncate text-[11px] text-[#80868b]">
                  {urlParts.path}
                </div>
              )}
            </div>
          </div>

          <h2 className="max-w-190 text-[20px] font-medium leading-[1.35] tracking-tight text-[#1a0dab] transition-all duration-150 group-hover:text-[#1558b0] group-hover:underline group-focus-visible:underline sm:text-[21px]">
            <HighlightedText
              text={title}
              query={query}
            />
          </h2>
        </a>
      ) : (
        <h2 className="max-w-190 text-[20px] font-medium leading-[1.35] tracking-tight text-[#202124] sm:text-[21px]">
          <HighlightedText
            text={title}
            query={query}
          />
        </h2>
      )}

      {result.snippet?.trim() && (
        <p className="mt-2.5 max-w-190 text-[14px] leading-[1.75] text-[#4d5156] sm:text-[15px]">
          <HighlightedText
            text={result.snippet.trim()}
            query={query}
          />
        </p>
      )}

      <div className="mt-3 flex items-center gap-2 text-[10px] text-[#9aa0a6] opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
        <span>Open result</span>

        <svg
          aria-hidden="true"
          className="h-3 w-3"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
        >
          <path d="M5 12h13" />
          <path d="m13 6 6 6-6 6" />
        </svg>
      </div>
    </article>
  );
}