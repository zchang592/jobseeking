import "server-only";
import { cookies } from "next/headers";
import { redirect, notFound } from "next/navigation";

export const backend = () =>
  process.env.RADAR_API_URL || "http://127.0.0.1:8170";
export async function read<T>(path: string): Promise<T> {
  const session = (await cookies()).get("radar_session");
  if (!session) redirect("/login");
  const result = await fetch(backend() + path, {
    headers: { cookie: "radar_session=" + encodeURIComponent(session.value) },
    cache: "no-store",
  });
  if (result.status === 401) redirect("/login");
  if (result.status === 404) notFound();
  if (!result.ok) throw new Error("读取招聘数据库失败");
  return result.json();
}
