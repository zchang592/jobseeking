export async function request<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const response = await fetch("/api" + path, {
    method,
    cache: "no-store",
    headers: { "Content-Type": "application/json", "X-Radar-Request": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "请求失败，请检查输入后重试",
    );
  return result as T;
}
