const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  accessToken: string | null,
  init: { method?: "GET" | "POST"; body?: unknown } = {},
): Promise<T> {
  if (!accessToken) throw new ApiError(401, "AUTH_REQUIRED", "Not signed in");
  const response = await fetch(`${API_URL}${path}`, {
    method: init.method ?? "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
    },
    body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    throw new ApiError(
      response.status,
      detail?.code ?? "HTTP_ERROR",
      detail?.message ?? (typeof detail === "string" ? detail : response.statusText),
    );
  }
  return payload as T;
}
