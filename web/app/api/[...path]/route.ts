import { NextRequest } from "next/server";
import { backend } from "@/lib/server";
type Context = { params: Promise<{ path: string[] }> };
async function forward(request: NextRequest, { params }: Context) {
  const path = (await params).path.join("/");
  if (
    !/^(health|session|overview|jobs(\/\d+)?|sources(\/\d+)?|activity|refresh|profile|brief|notices)$/.test(
      path,
    )
  )
    return Response.json({ detail: "接口不存在" }, { status: 404 });
  const headers = new Headers();
  const incoming = request.headers;
  if (request.method !== "GET") {
    if (
      incoming.get("X-Radar-Request") !== "1" ||
      incoming.get("sec-fetch-site") === "cross-site"
    )
      return Response.json({ detail: "请求校验失败" }, { status: 403 });
    headers.set("X-Radar-Request", "1");
    headers.set("Content-Type", "application/json");
  }
  headers.set("Cookie", incoming.get("cookie") || "");
  const body = request.method === "GET" ? undefined : await request.text();
  if (body && body.length > 12000)
    return Response.json({ detail: "请求过大" }, { status: 413 });
  try {
    const response = await fetch(
      backend() + "/" + path + request.nextUrl.search,
      {
        method: request.method,
        body,
        headers,
        cache: "no-store",
        redirect: "error",
      },
    );
    const outgoing = new Headers({
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    });
    const cookie = response.headers.get("set-cookie");
    if (cookie) outgoing.set("Set-Cookie", cookie);
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return Response.json({ detail: "采集服务连接失败" }, { status: 503 });
  }
}
export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
