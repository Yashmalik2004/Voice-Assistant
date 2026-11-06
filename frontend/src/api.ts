// Thin client for the Voice Assistant backend.
// Handles session creation and teardown with timeout support.

import type { SessionResponse } from "./types";

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

/** Default timeout for backend requests (ms). */
const REQUEST_TIMEOUT_MS = 10_000;

/**
 * Create a fetch request with an AbortController-based timeout.
 */
function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeoutMs = REQUEST_TIMEOUT_MS
): Promise<Response> {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal }).finally(() =>
    clearTimeout(id)
  );
}

/**
 * Create a new voice session and return LiveKit connection credentials.
 * Throws if the backend is unreachable or returns an error.
 */
export async function createSession(customerName?: string): Promise<SessionResponse> {
  let res: Response;
  try {
    res = await fetchWithTimeout(
      `${BACKEND_URL}/api/voice/session`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ customer_name: customerName ?? null }),
      }
    );
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error("Connection to Voice Assistant backend timed out. Is the backend running?");
    }
    throw new Error("Could not reach the Voice Assistant backend. Is it running?");
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      // non-JSON error body; keep the default message
    }
    throw new Error(detail);
  }

  return (await res.json()) as SessionResponse;
}

/**
 * End a session. Best-effort: failures here don't block the UI from resetting.
 */
export async function endSession(sessionId: string): Promise<void> {
  try {
    await fetchWithTimeout(
      `${BACKEND_URL}/api/voice/session/${sessionId}`,
      { method: "DELETE" },
      5_000
    );
  } catch {
    // ignore — session will expire naturally via TOKEN_TTL_SECONDS
  }
}
