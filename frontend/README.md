# Voice Assistant Widget

React + Vite embeddable voice support widget for the Voice Assistant application.

Connects to the FastAPI backend for a LiveKit token, joins the room, publishes
the microphone, plays the agent's audio, and shows a live transcript panel
(user turns right, agent turns left; interim text is dimmed until final).

## Features

- 🎙️ One-click voice call start
- 🔊 Real-time agent speech via LiveKit WebRTC
- 📝 Live transcript panel with interim and final segments
- 🔇 Mute/unmute control during calls
- ⚡ Barge-in support (interrupt the agent at any time)
- 🎯 Graceful audio unlock for browser autoplay policy compliance
- ⏱️ Request timeout with helpful error messages

## Setup

```bash
cd frontend
npm install
```

Configure the backend URL if not running on the default:

```bash
# frontend/.env.local
VITE_BACKEND_URL=http://localhost:8000
```

## Run

```bash
npm run dev     # http://localhost:5173
```

The backend (`uvicorn`) and the agent worker must be running and LiveKit
credentials configured for a full call to connect.

## Build

```bash
npm run build   # type-checks then produces dist/
```

The `dist/` directory contains the production-optimised static files.

## Architecture

```
VoiceWidget (UI)
  └── useVoiceSession (hook)
        ├── api.ts         — backend HTTP client (createSession, endSession)
        └── livekit-client — WebRTC audio + transcript text stream
```

The widget communicates with the backend only once at call start (to get a
LiveKit token), then uses WebRTC for all audio and transcript data. The backend
and agent communicate separately over the LiveKit server.

## Component Overview

| File | Purpose |
|------|---------|
| `App.tsx` | Demo page wrapper |
| `VoiceWidget.tsx` | Main widget UI (orb, transcript, controls) |
| `useVoiceSession.ts` | LiveKit session lifecycle hook |
| `api.ts` | Backend API client with timeout handling |
| `types.ts` | TypeScript type definitions |
| `widget.css` | Widget component styles |
| `demo.css` | Demo page layout styles |
