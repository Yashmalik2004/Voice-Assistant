// useVoiceSession — encapsulates the LiveKit room lifecycle for the widget.
//
// Responsibilities:
//   - request a token from the backend and connect to the room
//   - request mic permission and publish the microphone
//   - subscribe to and play the agent's audio track
//   - receive live transcripts over the lk.transcription text stream (M2)
//   - surface UI state (idle/connecting/listening/error/ended) + who's speaking
//   - clean disconnect + backend session teardown
//
// Barge-in visuals and agent responses build on this in later milestones.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  MediaDeviceFailure,
  RemoteParticipant,
  RemoteTrack,
  RemoteTrackPublication,
  Room,
  RoomEvent,
  Track,
  type Participant,
} from "livekit-client";

import { createSession, endSession } from "./api";
import type { Speaker, TranscriptSegment, WidgetState } from "./types";

// LiveKit transcription text-stream topic and segment attribute keys.
const TRANSCRIPTION_TOPIC = "lk.transcription";
const ATTR_SEGMENT_ID = "lk.segment_id";
const ATTR_FINAL = "lk.transcription_final";
// Agent lifecycle state, published by the agent as a participant attribute.
const ATTR_AGENT_STATE = "lk.agent.state";

interface VoiceSession {
  state: WidgetState;
  speaker: Speaker;
  transcripts: TranscriptSegment[];
  errorMessage: string | null;
  micMuted: boolean;
  needsAudioUnlock: boolean;
  start: (customerName?: string) => Promise<void>;
  hangUp: () => Promise<void>;
  toggleMic: () => void;
  unlockAudio: () => void;
  reset: () => void;
}

export function useVoiceSession(): VoiceSession {
  const [state, setState] = useState<WidgetState>("idle");
  const [speaker, setSpeaker] = useState<Speaker>("none");
  const [transcripts, setTranscripts] = useState<TranscriptSegment[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [micMuted, setMicMuted] = useState(false);
  const [needsAudioUnlock, setNeedsAudioUnlock] = useState(false);

  const roomRef = useRef<Room | null>(null);
  const sessionIdRef = useRef<string | null>(null);
  const localIdentityRef = useRef<string | null>(null);
  // Container that holds <audio> elements for remote (agent) tracks.
  const audioContainerRef = useRef<HTMLDivElement | null>(null);

  // Create the hidden audio sink once.
  useEffect(() => {
    const el = document.createElement("div");
    el.style.display = "none";
    el.setAttribute("data-Voice Assistant-audio-sink", "");
    document.body.appendChild(el);
    audioContainerRef.current = el;
    return () => {
      el.remove();
    };
  }, []);

  const fail = useCallback((message: string) => {
    setErrorMessage(message);
    setState("error");
  }, []);

  const cleanupRoom = useCallback(async () => {
    const room = roomRef.current;
    roomRef.current = null;
    if (room) {
      room.removeAllListeners();
      await room.disconnect();
    }
    if (audioContainerRef.current) {
      audioContainerRef.current.innerHTML = "";
    }
  }, []);

  const attachRemoteAudio = useCallback((track: RemoteTrack) => {
    if (track.kind !== Track.Kind.Audio) return;
    const element = track.attach();
    element.autoplay = true;
    audioContainerRef.current?.appendChild(element);
  }, []);

  // Insert or replace a transcript segment by id (interim updates replace).
  const upsertTranscript = useCallback((seg: TranscriptSegment) => {
    setTranscripts((prev) => {
      const idx = prev.findIndex((s) => s.id === seg.id);
      if (idx === -1) return [...prev, seg];
      const next = prev.slice();
      next[idx] = seg;
      return next;
    });
  }, []);

  // Register the LiveKit transcription text-stream handler. Each stream carries
  // one segment; chunks are text deltas we accumulate. The stream's attributes
  // tell us the segment id and whether it's final; the sender identity tells us
  // whether it's the customer (our local identity) or the agent.
  const registerTranscription = useCallback(
    (room: Room) => {
      room.registerTextStreamHandler(TRANSCRIPTION_TOPIC, async (reader, participantInfo) => {
        const attrs = reader.info.attributes ?? {};
        const segmentId = attrs[ATTR_SEGMENT_ID] || reader.info.id;
        const role: "user" | "agent" =
          participantInfo.identity === localIdentityRef.current ? "user" : "agent";

        let text = "";
        try {
          for await (const chunk of reader) {
            text += chunk;
            upsertTranscript({ id: segmentId, role, text, final: false });
          }
        } catch {
          // Stream aborted (e.g. on disconnect); keep whatever we accumulated.
        }

        const isFinal = attrs[ATTR_FINAL] === "true" || attrs[ATTR_FINAL] === undefined;
        upsertTranscript({ id: segmentId, role, text, final: isFinal });
      });
    },
    [upsertTranscript],
  );

  const start = useCallback(
    async (customerName?: string) => {
      setErrorMessage(null);
      setSpeaker("none");
      setTranscripts([]);
      setMicMuted(false);
      setNeedsAudioUnlock(false);
      setState("connecting");

      let session;
      try {
        session = await createSession(customerName);
      } catch (err) {
        fail(err instanceof Error ? err.message : "Could not start the session.");
        return;
      }

      sessionIdRef.current = session.session_id;
      localIdentityRef.current = session.participant_identity;

      const room = new Room({ adaptiveStream: true, dynacast: true });
      roomRef.current = room;

      // Register before connecting so we don't miss any early transcript streams.
      registerTranscription(room);

      room
        .on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
          attachRemoteAudio(track);
        })
        .on(
          RoomEvent.TrackUnsubscribed,
          (track: RemoteTrack, _pub: RemoteTrackPublication, _p: RemoteParticipant) => {
            track.detach().forEach((el) => el.remove());
          },
        )
        .on(RoomEvent.ActiveSpeakersChanged, (speakers: Participant[]) => {
          const localId = localIdentityRef.current;
          const localIsSpeaking = speakers.some((s) => s.identity === localId);
          if (localIsSpeaking) {
            // The customer speaking always wins the indicator — this is also
            // how a barge-in surfaces (user talks while agent is speaking).
            setSpeaker("user");
            return;
          }
          // Not the user. Defer to the agent's own state (set via attributes);
          // fall back to "none" only if the agent isn't actively speaking.
          setSpeaker((prev) => (prev === "agent" ? "agent" : "none"));
        })
        .on(
          RoomEvent.ParticipantAttributesChanged,
          (changed: Record<string, string>, participant: Participant) => {
            // Only the agent publishes lk.agent.state; ignore the local user.
            if (participant.identity === localIdentityRef.current) return;
            const agentState = changed[ATTR_AGENT_STATE] ?? participant.attributes[ATTR_AGENT_STATE];
            if (!agentState) return;
            // "speaking" -> show agent turn; anything else (listening/thinking/
            // idle) clears it unless the user is currently speaking.
            setSpeaker((prev) => {
              if (agentState === "speaking") return "agent";
              return prev === "user" ? "user" : "none";
            });
          },
        )
        .on(RoomEvent.AudioPlaybackStatusChanged, () => {
          setNeedsAudioUnlock(!room.canPlaybackAudio);
        })
        .on(RoomEvent.Disconnected, () => {
          // Only treat as "ended" if we weren't already in an error state.
          setState((prev) => (prev === "error" ? prev : "ended"));
          setSpeaker("none");
        });

      try {
        await room.connect(session.livekit_url, session.token);
      } catch (err) {
        await cleanupRoom();
        fail(
          err instanceof Error
            ? `Could not connect to the voice service: ${err.message}`
            : "Could not connect to the voice service.",
        );
        return;
      }

      // Request mic permission and publish. This may prompt the browser.
      try {
        await room.localParticipant.setMicrophoneEnabled(true);
      } catch (err) {
        const failure = MediaDeviceFailure.getFailure(err);
        await cleanupRoom();
        if (failure === MediaDeviceFailure.PermissionDenied) {
          fail("Microphone access was blocked. Please allow the mic and try again.");
        } else if (failure === MediaDeviceFailure.NotFound) {
          fail("No microphone was found. Please connect one and try again.");
        } else if (failure === MediaDeviceFailure.DeviceInUse) {
          fail("Your microphone is in use by another app. Close it and try again.");
        } else {
          fail("Could not access your microphone. Please check permissions.");
        }
        return;
      }

      setNeedsAudioUnlock(!room.canPlaybackAudio);
      setState("listening");
    },
    [attachRemoteAudio, cleanupRoom, fail, registerTranscription],
  );

  const hangUp = useCallback(async () => {
    const sessionId = sessionIdRef.current;
    await cleanupRoom();
    if (sessionId) {
      await endSession(sessionId);
      sessionIdRef.current = null;
    }
    setSpeaker("none");
    setState("ended");
  }, [cleanupRoom]);

  const toggleMic = useCallback(() => {
    const room = roomRef.current;
    if (!room) return;
    const next = !micMuted;
    void room.localParticipant.setMicrophoneEnabled(!next);
    setMicMuted(next);
  }, [micMuted]);

  const unlockAudio = useCallback(() => {
    const room = roomRef.current;
    if (!room) return;
    void room.startAudio().then(() => setNeedsAudioUnlock(!room.canPlaybackAudio));
  }, []);

  const reset = useCallback(() => {
    setErrorMessage(null);
    setSpeaker("none");
    setTranscripts([]);
    setMicMuted(false);
    setNeedsAudioUnlock(false);
    setState("idle");
  }, []);

  // Tear down on unmount so we don't leave a dangling room connection.
  useEffect(() => {
    return () => {
      const sessionId = sessionIdRef.current;
      void cleanupRoom();
      if (sessionId) void endSession(sessionId);
    };
  }, [cleanupRoom]);

  return {
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
  };
}
