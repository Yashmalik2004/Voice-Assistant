"""Voice Assistant LiveKit agent worker.

Milestone 5 — full grounded conversation loop:
Registers with the LiveKit server under an explicit agent name, joins the
dispatched room, and runs the complete voice pipeline via `AgentSession`:
  - Deepgram streaming STT transcribes the customer (M2), forwarded to the
    widget over the `lk.transcription` text stream.
  - Cartesia streaming TTS speaks responses back (M3).
  - Silero-VAD turn-taking + barge-in (M4).
  - An OpenAI LLM with function tools is the reasoning layer (M5): it classifies
    intent and calls tools against the backend for grounded order/policy data,
    so spoken facts are never hallucinated. See `support_agent.SupportAgent`.

Graceful degradation: STT is required. Without a Cartesia key the agent
transcribes but can't speak. Without an OpenAI key there is no reasoning LLM,
so the agent falls back to a spoken notice rather than answering.

Run:
    uv run python -m Voice Assistant_agent.worker start
"""

from __future__ import annotations

import logging

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    MetricsCollectedEvent,
    RoomInputOptions,
    RoomOutputOptions,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.voice.events import AgentStateChangedEvent, UserInputTranscribedEvent
from livekit.plugins import cartesia, deepgram, openai, silero

from . import config
from .support_agent import SupportAgent

logger = logging.getLogger("Voice Assistant.agent")


def _build_stt() -> deepgram.STT:
    return deepgram.STT(
        model=config.STT_MODEL,
        language=config.STT_LANGUAGE,
        interim_results=True,
        api_key=config.DEEPGRAM_API_KEY,
    )


def _build_tts() -> cartesia.TTS:
    return cartesia.TTS(
        model=config.TTS_MODEL,
        voice=config.TTS_VOICE,
        language=config.TTS_LANGUAGE,
        api_key=config.CARTESIA_API_KEY,
    )


def _build_llm() -> openai.LLM:
    return openai.LLM(model=config.LLM_MODEL, api_key=config.OPENAI_API_KEY)


async def entrypoint(ctx: JobContext) -> None:
    """Job entrypoint: connect and run the full grounded conversation loop."""
    logger.info("Agent job starting for room: %s", ctx.room.name)

    if not config.stt_configured():
        logger.error(
            "DEEPGRAM_API_KEY is not set. The STT pipeline cannot run. "
            "Set it in the repo-root .env and restart the worker."
        )
        await ctx.connect()
        return

    has_tts = config.tts_configured()
    has_llm = config.llm_configured()
    if not has_tts:
        logger.warning("CARTESIA_API_KEY not set — the agent will transcribe but not speak.")
    if not has_llm:
        logger.warning(
            "OPENAI_API_KEY not set — no reasoning LLM. The agent will greet and "
            "explain it can't answer questions right now."
        )

    session: AgentSession = AgentSession(
        stt=_build_stt(),
        llm=_build_llm() if has_llm else None,
        tts=_build_tts() if has_tts else None,
        vad=silero.VAD.load(),
        turn_handling={
            "turn_detection": "vad",
            "endpointing": {
                "min_delay": config.TURN_ENDPOINTING_DELAY,
                "max_delay": config.TURN_MAX_DELAY,
            },
            "interruption": {
                "enabled": config.INTERRUPTIONS_ENABLED,
                "min_duration": config.MIN_INTERRUPTION_DURATION,
            },
        },
        # Strip any markdown/symbols the LLM emits before it reaches TTS.
        tts_text_transforms=["filter_markdown", "filter_emoji"],
    )

    @session.on("user_input_transcribed")
    def _on_transcript(ev: UserInputTranscribedEvent) -> None:
        if ev.is_final:
            logger.info("FINAL   [%s]: %s", ev.speaker_id or "user", ev.transcript)
        else:
            logger.debug("interim [%s]: %s", ev.speaker_id or "user", ev.transcript)

    @session.on("agent_state_changed")
    def _on_agent_state(ev: AgentStateChangedEvent) -> None:
        # A jump from speaking back to listening mid-reply is a successful barge-in.
        logger.info("agent state: %s -> %s", ev.old_state, ev.new_state)

    # Aggregate usage/latency across the session for an end-of-call summary.
    usage = metrics.ModelUsageCollector()

    @session.on("metrics_collected")
    def _on_metrics(ev: MetricsCollectedEvent) -> None:
        # Per-stage latency + usage (spec 5.4). log_metrics surfaces LLM
        # time-to-first-token and TTS time-to-first-byte, which together with
        # the STT end-of-turn are the STT->LLM->TTS round trip. STT metrics are
        # noisy per-frame, so skip them here.
        if ev.metrics.type == "stt_metrics":
            return
        metrics.log_metrics(ev.metrics)
        usage.collect(ev.metrics)

    async def _log_usage_summary() -> None:
        logger.info("Session usage summary: %s", usage.flatten())

    ctx.add_shutdown_callback(_log_usage_summary)

    # With an LLM, SupportAgent's tools + persona drive the conversation and its
    # on_enter greets the caller. Without an LLM, a plain Agent just greets and
    # explains it can't answer (via session.say below).
    agent: Agent = SupportAgent() if has_llm else Agent(
        instructions=(
            f"You are {config.AGENT_PERSONA_NAME} from {config.STORE_NAME} support."
        )
    )

    await ctx.connect()
    logger.info(
        "Connected to room %s as %s; starting session (STT%s%s)",
        ctx.room.name,
        ctx.room.local_participant.identity,
        " + TTS" if has_tts else "",
        " + LLM" if has_llm else "",
    )

    await session.start(
        agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(audio_enabled=True),
        room_output_options=RoomOutputOptions(
            transcription_enabled=True,
            sync_transcription=has_tts,
            audio_enabled=has_tts,
        ),
    )
    logger.info("Session started for room %s", ctx.room.name)

    # When there's no LLM, SupportAgent.on_enter won't run its reply flow, so
    # speak a fallback notice directly (only if TTS is available).
    if not has_llm and has_tts:
        await session.say(
            f"{config.GREETING} I'm having trouble reaching my knowledge base "
            "right now, so I can't answer questions at the moment."
        )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name=config.AGENT_NAME,
        )
    )


if __name__ == "__main__":
    main()
