import { NextRequest, NextResponse } from "next/server";

const SEARCH_API_URL =
  process.env.SEARCH_API_URL ??
  "http://localhost:8000";

export async function GET(
  request: NextRequest,
) {
  const searchParams =
    request.nextUrl.searchParams;

  const query =
    searchParams.get("q")?.trim();

  const mode =
    searchParams.get("mode") ??
    "hybrid";

  const limit =
    searchParams.get("limit") ??
    "10";

  if (!query) {
    return NextResponse.json(
      {
        detail: "Query must not be empty.",
      },
      {
        status: 400,
      },
    );
  }

  const params = new URLSearchParams({
    q: query,
    mode,
    limit,
  });

  try {
    const response = await fetch(
      `${SEARCH_API_URL.replace(/\/$/, "")}/search?${params.toString()}`,
      {
        cache: "no-store",
      },
    );

    const body = await response
      .json()
      .catch(() => ({
        detail:
          "Search service returned an invalid response.",
      }));

    return NextResponse.json(
      body,
      {
        status: response.status,
      },
    );
  } catch {
    return NextResponse.json(
      {
        detail:
          "Search service is currently unavailable.",
      },
      {
        status: 503,
      },
    );
  }
}