"""FastAPI backend for the Chatterbox voice agent.

Serves the TTS model over HTTP so a remote frontend (Vercel) can call it
through a Cloudflare tunnel.

Run:  .venv\\Scripts\\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000
"""
import os
import struct
import tempfile
import threading

import torch
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from chatterbox.tts_turbo import ChatterboxTurboTTS

from tts_utils import chunk_text

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
    if ref_audio is not None:
        suffix = os.path.splitext(ref_audio.filename or "ref.wav")[1] or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(ref_audio.file.read())
            ref_path = f.name
        # validate before streaming starts — errors can't become 4xx afterwards
        import librosa
        try:
            duration = librosa.get_duration(path=ref_path)
        except Exception:
            os.unlink(ref_path)
            raise HTTPException(status_code=400, detail="Could not read reference audio")
        if duration <= 5.0:
            os.unlink(ref_path)
            raise HTTPException(status_code=400, detail="Reference clip must be longer than 5 seconds")

    chunks = chunk_text(text.strip())
    temp = max(0.05, min(2.0, temperature))

    # Stream the WAV as it's generated: intermediaries (Cloudflare tunnel,
    # Vercel) time out connections that stay silent for ~100s, and long
    # texts take minutes to synthesize in full.
    def wav_stream():
        try:
            yield _wav_header(MODEL.sr)
            with GEN_LOCK:
                if ref_path is None and DEFAULT_CONDS is not None:
                    MODEL.conds = DEFAULT_CONDS
                for i, chunk in enumerate(chunks):
                    print(f"chunk {i + 1}/{len(chunks)}")
                    wav = MODEL.generate(
                        chunk,
                        audio_prompt_path=ref_path if i == 0 else None,
                        temperature=temp,
                    )
                    pcm = (wav.squeeze(0).clamp(-1, 1) * 32767).to(torch.int16)
                    yield pcm.cpu().numpy().tobytes()
        finally:
            if ref_path:
                try:
                    os.unlink(ref_path)
                except OSError:
                    pass

    return StreamingResponse(wav_stream(), media_type="audio/wav")


def _wav_header(sr: int, channels: int = 1, bits: int = 16) -> bytes:
    """RIFF/WAVE header with 'unknown' (max) sizes — the streaming-WAV
    convention; decoders read PCM until the stream ends."""
    byte_rate = sr * channels * bits // 8
    block_align = channels * bits // 8
    return (
        b"RIFF" + struct.pack("<I", 0xFFFFFFFF) + b"WAVE"
        + b"fmt " + struct.pack("<IHHIIHH", 16, 1, channels, sr, byte_rate, block_align, bits)
        + b"data" + struct.pack("<I", 0xFFFFFFFF)
    )
