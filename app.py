"""Simple voice agent UI built on Resemble AI's Chatterbox TTS.

Auto-selects the model for your hardware:
  - NVIDIA GPU available -> Chatterbox-Turbo (350M, low latency)
  - CPU only             -> Chatterbox-Nano  (110M, ~3x realtime on 8 cores)

Run:  python app.py   then open http://127.0.0.1:7860
"""
import random

import numpy as np
import torch
import gradio as gr
from chatterbox.tts_turbo import ChatterboxTurboTTS

from tts_utils import ensure_readable_audio, generate_long

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
USE_NANO = DEVICE == "cpu"
MODEL_NAME = "Chatterbox-Nano (CPU)" if USE_NANO else "Chatterbox-Turbo (GPU)"

EVENT_TAGS = [
    "[chuckle]", "[laugh]", "[sigh]", "[cough]", "[clear throat]",
    "[sniff]", "[gasp]", "[groan]", "[shush]",
]

MODEL = None
DEFAULT_CONDS = None


def get_model():
    global MODEL, DEFAULT_CONDS
    if MODEL is None:
        print(f"Loading {MODEL_NAME} on {DEVICE} (first run downloads weights)...")
        MODEL = ChatterboxTurboTTS.from_pretrained(device=DEVICE, nano=USE_NANO)
        DEFAULT_CONDS = MODEL.conds
        print("Model ready.")
    return MODEL


def set_seed(seed: int):
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    random.seed(seed)
    np.random.seed(seed)


def speak(text, ref_audio, temperature, seed):
    if not text or not text.strip():
        raise gr.Error("Please enter some text to speak.")
    model = get_model()
    if seed and int(seed) != 0:
        set_seed(int(seed))
    cleanup = None
    if ref_audio:
        try:
            ref_audio, cleanup = ensure_readable_audio(ref_audio)
        except RuntimeError as e:
            raise gr.Error(str(e))
    try:
        wav = generate_long(
            model,
            text.strip(),
            audio_prompt_path=ref_audio,
            temperature=temperature,
            default_conds=DEFAULT_CONDS,
        )
    finally:
        if cleanup:
            try:
                import os
                os.unlink(cleanup)
            except OSError:
                pass
    return (model.sr, wav.squeeze(0).numpy())


with gr.Blocks(title="Voice Agent — Chatterbox TTS") as demo:
    gr.Markdown(
        f"# 🎙️ Voice Agent\n"
        f"Powered by **{MODEL_NAME}**. Type text, optionally add a ~10s reference "
        f"clip to clone a voice, and press **Speak**. Use the tag buttons for "
        f"expressions like laughter."
    )

    with gr.Row():
        with gr.Column():
            text = gr.Textbox(
                label="Text to speak",
                value="Hi there! [chuckle] I'm your new voice agent, running locally on your machine. What can I do for you today?",
                lines=4,
                elem_id="main_textbox",
            )
            with gr.Row():
                tag_buttons = [gr.Button(t, size="sm") for t in EVENT_TAGS]

            ref_audio = gr.Audio(
                sources=["upload", "microphone"],
                type="filepath",
                label="Reference voice (optional, 5-15s clip to clone; leave empty for default voice)",
            )
            speak_btn = gr.Button("🔊 Speak", variant="primary")

        with gr.Column():
            audio_out = gr.Audio(label="Generated speech", autoplay=True)
            with gr.Accordion("Advanced", open=False):
                temperature = gr.Slider(0.05, 2.0, value=0.8, step=0.05, label="Temperature")
                seed = gr.Number(value=0, label="Seed (0 = random)")

    INSERT_TAG_JS = """
    (tag_val, current_text) => {
        const ta = document.querySelector('#main_textbox textarea');
        if (!ta) return current_text + " " + tag_val;
        const start = ta.selectionStart, end = ta.selectionEnd;
        let prefix = (start === 0 || current_text[start - 1] === ' ') ? '' : ' ';
        let suffix = (end < current_text.length && current_text[end] === ' ') ? '' : ' ';
        return current_text.slice(0, start) + prefix + tag_val + suffix + current_text.slice(end);
    }
    """
    for btn in tag_buttons:
        btn.click(fn=None, inputs=[btn, text], outputs=text, js=INSERT_TAG_JS)

    speak_btn.click(
        fn=speak,
        inputs=[text, ref_audio, temperature, seed],
        outputs=audio_out,
    )

    demo.load(fn=lambda: get_model() and None)

if __name__ == "__main__":
    demo.queue(default_concurrency_limit=1).launch(server_name="127.0.0.1", server_port=7860)
