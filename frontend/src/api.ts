// Thin client for the Voice Assistant backend.

import type { SessionResponse } from "./types";

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

export async function createSession(customerName?: string): Promise<SessionResponse> {
  const res = await fetch(`${BACKEND_URL}/api/voice/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ customer_name: customerName ?? null }),
  });

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

export async function endSession(sessionId: string): Promise<void> {
  // Best-effort; failures here shouldn't block the UI from returning to idle.
  try {
    await fetch(`${BACKEND_URL}/api/voice/session/${sessionId}`, {
      method: "DELETE",
    });
  } catch {
    // ignore
  }
}
