"""Shared helpers for long-form TTS generation.

Chatterbox generates best on short passages (~300 chars) and silently
truncates long inputs, so long text is split on sentence boundaries and
the per-chunk audio is concatenated.
"""
import glob
import os
import re
import shutil
import subprocess
import tempfile

import torch

MAX_CHUNK_CHARS = 280

# [pause] is not a model tag — it's rendered as real silence between
# generated segments. Consecutive tags accumulate.
PAUSE_SECONDS = 0.6
_PAUSE_RE = re.compile(r"\[pause\]", re.IGNORECASE)


def split_on_pauses(text: str) -> list[tuple[str, object]]:
    """Split text into ("text", chunk) and ("pause", seconds) items."""
    items = []
    parts = _PAUSE_RE.split(text)
    for i, part in enumerate(parts):
        if i > 0:
            if items and items[-1][0] == "pause":
                items[-1] = ("pause", items[-1][1] + PAUSE_SECONDS)
            else:
                items.append(("pause", PAUSE_SECONDS))
        for chunk in chunk_text(part):
            items.append(("text", chunk))
    return items


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    # winget installs aren't on PATH until the next login; look there directly
    pattern = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\**\bin\ffmpeg.exe"
    )
    hits = glob.glob(pattern, recursive=True)
    return hits[0] if hits else None


def ensure_readable_audio(path):
    """Return (usable_path, temp_path_to_cleanup).

    The model's loader (libsndfile) can't read m4a/aac and similar formats;
    transcode those to WAV with ffmpeg. temp_path_to_cleanup is None when
    the original file was usable as-is.
    """
    import soundfile as sf
    try:
        sf.info(path)
        return path, None
    except Exception:
        pass
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("Unsupported audio format (and ffmpeg is not installed to convert it)")
    out = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    out.close()
    r = subprocess.run(
        [ffmpeg, "-y", "-i", path, "-ar", "44100", "-ac", "1", "-c:a", "pcm_s16le", out.name],
        capture_output=True,
    )
    if r.returncode != 0:
        os.unlink(out.name)
        raise RuntimeError("Could not decode the reference audio file")
    return out.name, out.name


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    sentences = re.split(r"(?<=[.!?…。！？])\s+", text.strip())
    chunks, cur = [], ""
    for s in sentences:
        # hard-split a single sentence that alone exceeds the budget
        while len(s) > max_chars:
            cut = s.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            if cur:
                chunks.append(cur)
                cur = ""
            chunks.append(s[:cut])
            s = s[cut:].lstrip()
        if not cur:
            cur = s
        elif len(cur) + 1 + len(s) <= max_chars:
            cur += " " + s
        else:
            chunks.append(cur)
            cur = s
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


def generate_long(model, text, audio_prompt_path=None, temperature=0.8,
                  default_conds=None, on_progress=None):
    """Generate speech for arbitrarily long text, one chunk at a time.

    The reference clip is embedded once (first chunk); later chunks reuse
    the model's stored conditionals. When no reference is given, restore
    `default_conds` so a clone from an earlier request doesn't leak in.
    """
    items = split_on_pauses(text)
    if audio_prompt_path is None and default_conds is not None:
        model.conds = default_conds
    wavs = []
    first_text = True
    for i, (kind, val) in enumerate(items):
        if on_progress:
            on_progress(i, len(items))
        if kind == "pause":
            wavs.append(torch.zeros(1, int(model.sr * val)))
            continue
        wavs.append(model.generate(
            val,
            audio_prompt_path=audio_prompt_path if first_text else None,
            temperature=temperature,
        ))
        first_text = False
    return torch.cat(wavs, dim=1)
