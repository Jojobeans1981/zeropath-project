const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ApiError {
  code: string;
  message: string;
}

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  try {
    const res = await fetch(`${API_URL}${endpoint}`, {
      ...options,
      headers,
    });

    const body = await res.json();

    if (!res.ok) {
      if (res.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
      }
      return {
        success: false,
        error: body.error || body.detail || { code: "UNKNOWN", message: "An unexpected error occurred." },
      };
    }

    return { success: true, data: body.data !== undefined ? body.data : body };
  } catch (err) {
    return {
      success: false,
      error: { code: "NETWORK_ERROR", message: err instanceof Error ? err.message : "Network error" },
    };
  }
}
