import { getServerSession } from "next-auth";
import { authOptions } from "@/lib/auth";
import { internalToken } from "@/lib/internal-token";

type RouteContext = { params: Promise<{ path: string[] }> };

async function proxy(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  const route = `/${path.join("/")}`;
  const publicRoute = route === "/health" || (request.method === "GET" && route.startsWith("/products"));
  const publicAuthRoute = request.method === "POST" && [
    "/auth/register", "/auth/verify-email", "/auth/verification/request", "/auth/password-reset/request", "/auth/password-reset/confirm",
  ].includes(route);
  const allowed = publicRoute || publicAuthRoute || route === "/search" || route.startsWith("/search/") || route === "/shopify" || route.startsWith("/dev/observability/");
  if (!allowed) return Response.json({ detail: "Not found" }, { status: 404 });

  const session = publicRoute || publicAuthRoute ? null : await getServerSession(authOptions);
  if (!publicRoute && !publicAuthRoute && !session?.user?.id) {
    return Response.json({ detail: "Authentication required" }, { status: 401 });
  }
  const incomingUrl = new URL(request.url);
  const upstream = new URL(route, process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000");
  upstream.search = incomingUrl.search;
  const headers = new Headers();
  if (request.headers.has("content-type")) headers.set("content-type", request.headers.get("content-type")!);
  if (session?.user?.id) headers.set("authorization", `Bearer ${internalToken(session.user.id, { sv: session.user.authVersion })}`);
  try {
    const response = await fetch(upstream, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.text(),
      cache: "no-store",
      redirect: "manual",
    });
    const responseHeaders = new Headers();
    for (const name of ["content-type", "retry-after", "x-request-id"]) {
      const value = response.headers.get(name);
      if (value) responseHeaders.set(name, value);
    }
    responseHeaders.set("cache-control", "no-store");
    return new Response(response.body, { status: response.status, headers: responseHeaders });
  } catch {
    return Response.json({ detail: "Backend is unavailable" }, { status: 503 });
  }
}

export { proxy as GET, proxy as POST, proxy as PUT, proxy as PATCH, proxy as DELETE };
