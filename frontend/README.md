# Voice Assistant Widget

React + Vite embeddable voice support widget. Connects to the FastAPI backend
for a LiveKit token, joins the room, publishes the microphone, plays the agent's
audio, and shows a live transcript panel (user turns right, agent turns left;
interim text is dimmed until final) fed by the `lk.transcription` text stream.

## Setup

```bash
cd frontend
npm install
```

Create `frontend/.env.local` (or set the var in your shell) if your backend is
not on the default:

```
VITE_BACKEND_URL=http://localhost:8000
```

## Run

```bash
npm run dev     # http://localhost:5173
```

The backend (`uvicorn`) and the agent worker must be running, and LiveKit
credentials configured, for a full call to connect.

## Build

```bash
npm run build   # type-checks then produces dist/
```
