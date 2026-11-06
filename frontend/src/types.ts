// Shared frontend types.

// Widget UI states (spec section 6.2).
export type WidgetState =
  | "idle"
  | "connecting"
  | "listening" // connected; either party may be speaking
  | "error"
  | "ended";

// Response shape from the backend POST /api/voice/session.
export interface SessionResponse {
  session_id: string;
  room_name: string;
  participant_identity: string;
  token: string;
  livekit_url: string;
  expires_at: string;
}

// Who is currently speaking, for the turn indicator.
export type Speaker = "none" | "user" | "agent";

// A single transcript segment shown in the live transcript panel.
export interface TranscriptSegment {
  // Stable id per segment so interim updates replace, not duplicate.
  id: string;
  // "user" for the customer, "agent" for Voice Assistant.
  role: "user" | "agent";
  text: string;
  // False while the segment is still being spoken/refined.
  final: boolean;
}
