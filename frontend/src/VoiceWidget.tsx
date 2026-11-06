// VoiceWidget — the embeddable Voice Assistant call UI.

import { useEffect, useRef } from "react";

import { useVoiceSession } from "./useVoiceSession";
import type { Speaker, TranscriptSegment, WidgetState } from "./types";

function StatusLine({ state, speaker }: { state: WidgetState; speaker: Speaker }) {
  const text: Record<WidgetState, string> = {
    idle: "Talk to support",
    connecting: "Connecting…",
    listening:
      speaker === "agent"
        ? "Agent is speaking…"
        : speaker === "user"
          ? "Listening…"
          : "Connected — go ahead and speak",
    error: "Something went wrong",
    ended: "Call ended",
  };
  return <p className="vd-status">{text[state]}</p>;
}

function Orb({ state, speaker }: { state: WidgetState; speaker: Speaker }) {
  const cls = [
    "vd-orb",
    state === "connecting" ? "vd-orb--connecting" : "",
    state === "listening" && speaker === "user" ? "vd-orb--user" : "",
    state === "listening" && speaker === "agent" ? "vd-orb--agent" : "",
    state === "error" ? "vd-orb--error" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={cls} aria-hidden="true">
      <span className="vd-orb__pulse" />
      <span className="vd-orb__mic">🎙️</span>
    </div>
  );
}

function Transcript({ segments }: { segments: TranscriptSegment[] }) {
  const endRef = useRef<HTMLDivElement | null>(null);

  // Keep the newest line in view as transcripts stream in.
  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [segments]);

  if (segments.length === 0) {
    return (
      <div className="vd-transcript vd-transcript--empty">
        <p>Your conversation will appear here.</p>
      </div>
    );
  }

  return (
    <div className="vd-transcript" aria-live="polite" aria-label="Live transcript">
      {segments.map((seg) => (
        <div
          key={seg.id}
          className={`vd-line vd-line--${seg.role} ${seg.final ? "" : "vd-line--interim"}`}
        >
          <span className="vd-line__who">{seg.role === "user" ? "You" : "Agent"}</span>
          <span className="vd-line__text">{seg.text}</span>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

export function VoiceWidget() {
  const {
    state,
    speaker,
    transcripts,
    errorMessage,
    micMuted,
    needsAudioUnlock,
    start,
    hangUp,
    toggleMic,
    unlockAudio,
    reset,
  } = useVoiceSession();

  const inCall = state === "listening" || state === "connecting";
  const showTranscript = state === "listening" || state === "ended";

  return (
    <div className="vd-card" role="region" aria-label="Voice support">
      <div className="vd-header">
        <span className="vd-brand">Voice Assistant</span>
        <span className="vd-sub">Order support</span>
      </div>

      <Orb state={state} speaker={speaker} />
      <StatusLine state={state} speaker={speaker} />

      {state === "error" && errorMessage && (
        <p className="vd-error" role="alert">
          {errorMessage}
        </p>
      )}

      {needsAudioUnlock && inCall && (
        <button className="vd-btn vd-btn--ghost" onClick={unlockAudio}>
          Tap to enable audio
        </button>
      )}

      {showTranscript && <Transcript segments={transcripts} />}

      <div className="vd-actions">
        {state === "idle" && (
          <button className="vd-btn vd-btn--primary" onClick={() => void start()}>
            Start call
          </button>
        )}

        {state === "connecting" && (
          <button className="vd-btn vd-btn--danger" onClick={() => void hangUp()}>
            Cancel
          </button>
        )}

        {state === "listening" && (
          <>
            <button
              className={`vd-btn ${micMuted ? "vd-btn--ghost" : "vd-btn--secondary"}`}
              onClick={toggleMic}
              aria-pressed={micMuted}
            >
              {micMuted ? "Unmute" : "Mute"}
            </button>
            <button className="vd-btn vd-btn--danger" onClick={() => void hangUp()}>
              Hang up
            </button>
          </>
        )}

        {(state === "ended" || state === "error") && (
          <button className="vd-btn vd-btn--primary" onClick={reset}>
            {state === "error" ? "Try again" : "New call"}
          </button>
        )}
      </div>

      <p className="vd-hint">
        {state === "idle"
          ? "Ask about an order, a return, or a product."
          : "You can interrupt the agent at any time."}
      </p>
    </div>
  );
}
