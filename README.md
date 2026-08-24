# Voice Agent (Chatterbox TTS)

A simple local web UI around [Resemble AI's Chatterbox](https://github.com/resemble-ai/chatterbox) text-to-speech models.

- With an NVIDIA GPU it uses **Chatterbox-Turbo** (350M, low latency).
- On CPU it uses **Chatterbox-Nano** (110M, ~3x realtime on 8 cores).

Both support paralinguistic tags like `[chuckle]`, `[laugh]`, `[sigh]` and zero-shot voice cloning from a ~10 second reference clip.

## Setup (one time)

```powershell
.\setup.ps1
```

This creates a `.venv` virtual environment and installs the cloned `chatterbox` repo into it.

## Run

```powershell
.\run.ps1
```

Then open http://127.0.0.1:7860 in your browser.

The first generation downloads the model weights from Hugging Face (a few GB), so it takes a while once; afterwards it's fast.

## Using the UI

1. Type the text you want spoken. Click the tag buttons (`[laugh]`, etc.) to insert expressions at the cursor.
2. Optionally upload or record a ~10 second reference clip to clone that voice. Leave empty for the default voice.
3. Press **Speak** — the audio plays automatically and can be downloaded.

Advanced: temperature controls expressiveness/variation; set a non-zero seed for reproducible output.

All generated audio carries Resemble's imperceptible PerTh watermark (responsible-AI feature of the model).

## Public site (Vercel)

The UI is also deployed at **https://voice-agent-henna-eight.vercel.app** — the page is always up, but speech generation runs on this PC's GPU, reached through a Cloudflare tunnel.

To bring the backend online:

```powershell
.\start-backend.ps1
```

This starts the TTS API server (`server.py` on port 8000), opens a Cloudflare quick tunnel, points the Vercel deployment at the new tunnel URL, and redeploys. Keep the window open; Ctrl+C stops serving. Because quick-tunnel URLs change on every start, the script re-runs the Vercel env update + redeploy each time.

Pieces:
- `server.py` — FastAPI wrapper around the model (`POST /tts`, guarded by the key in `.backend-key`)
- `web/` — the Vercel site: static `index.html` + `api/tts.js` serverless proxy that injects the key
- Vercel project: `voice-agent` (env vars `BACKEND_URL`, `BACKEND_KEY`; note they're "sensitive" so `vercel env pull` shows them blank — that's normal)
