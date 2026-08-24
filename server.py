"""FastAPI backend for the Chatterbox voice agent.

Serves the TTS model over HTTP so a remote frontend (Vercel) can call it
through a Cloudflare tunnel.

Run:  .venv\\Scripts\\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
"""
import io
import os
import tempfile
import threading

import torch
import torchaudio
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response

from chatterbox.tts_turbo import ChatterboxTurboTTS

from tts_utils import generate_long

API_KEY = os.getenv("VOICE_AGENT_KEY", "")
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
USE_NANO = DEVICE == "cpu"
MAX_TEXT_CHARS = 10_000

app = FastAPI(title="Voice Agent API")
MODEL = None
DEFAULT_CONDS = None
# generate() mutates model state (conditionals), so serialize requests
GEN_LOCK = threading.Lock()


@app.on_event("startup")
def load_model():
    global MODEL, DEFAULT_CONDS
    print(f"Loading Chatterbox-{'Nano' if USE_NANO else 'Turbo'} on {DEVICE}...")
    MODEL = ChatterboxTurboTTS.from_pretrained(device=DEVICE, nano=USE_NANO)
    DEFAULT_CONDS = MODEL.conds
    print("Model ready.")


@app.get("/health")
def health():
    return {"ok": True, "device": DEVICE, "model_loaded": MODEL is not None}


@app.post("/tts")
def tts(
    text: str = Form(...),
    temperature: float = Form(0.8),
    ref_audio: UploadFile | None = File(None),
    x_api_key: str = Header(default=""),
):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(status_code=400, detail=f"Text too long (max {MAX_TEXT_CHARS} chars)")

    ref_path = None
    try:
        if ref_audio is not None:
            suffix = os.path.splitext(ref_audio.filename or "ref.wav")[1] or ".wav"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(ref_audio.file.read())
                ref_path = f.name

        with GEN_LOCK:
            wav = generate_long(
                MODEL,
                text.strip(),
                audio_prompt_path=ref_path,
                temperature=max(0.05, min(2.0, temperature)),
                default_conds=DEFAULT_CONDS,
                on_progress=lambda i, n: print(f"chunk {i + 1}/{n}"),
            )
    except AssertionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if ref_path:
            try:
                os.unlink(ref_path)
            except OSError:
                pass

    buf = io.BytesIO()
    # 16-bit PCM halves the payload vs float32 — matters for long texts
    torchaudio.save(buf, wav, MODEL.sr, format="wav", encoding="PCM_S", bits_per_sample=16)
    return Response(content=buf.getvalue(), media_type="audio/wav")
