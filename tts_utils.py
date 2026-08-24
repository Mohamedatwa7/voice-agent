"""Shared helpers for long-form TTS generation.

Chatterbox generates best on short passages (~300 chars) and silently
truncates long inputs, so long text is split on sentence boundaries and
the per-chunk audio is concatenated.
"""
import re

import torch

MAX_CHUNK_CHARS = 280


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
    chunks = chunk_text(text)
    if audio_prompt_path is None and default_conds is not None:
        model.conds = default_conds
    wavs = []
    for i, chunk in enumerate(chunks):
        if on_progress:
            on_progress(i, len(chunks))
        wavs.append(model.generate(
            chunk,
            audio_prompt_path=audio_prompt_path if i == 0 else None,
            temperature=temperature,
        ))
    return torch.cat(wavs, dim=1)
