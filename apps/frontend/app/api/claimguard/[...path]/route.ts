import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.CLAIMGUARD_API_URL ?? "http://127.0.0.1:8000";
const API_KEY = process.env.CLAIMGUARD_API_KEY ?? "claimguard-local";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const { path } = await context.params;
  const upstream = new URL(`${API_URL}/${path.join("/")}`);
  upstream.search = request.nextUrl.search;

  const headers = new Headers();
  headers.set("X-API-Key", API_KEY);
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers.set("content-type", contentType);
  }

  const init: RequestInit = { method: request.method, headers };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.arrayBuffer();
  }

  try {
    const response = await fetch(upstream, init);
    const body = await response.arrayBuffer();
    return new NextResponse(body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "upstream unavailable";
    return NextResponse.json({ detail: `API unreachable: ${message}` }, { status: 502 });
  }
}

export async function GET(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxy(request, context);
}
