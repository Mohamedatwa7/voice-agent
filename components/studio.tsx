"use client";

import { motion } from "framer-motion";
import { ArrowRight, LoaderCircle, Mic, Volume2 } from "lucide-react";
import { useRef, useState } from "react";
import { WordsPullUp } from "@/components/ui/prisma-hero";

const TAGS = [
  "[pause]",
  "[chuckle]",
  "[laugh]",
  "[sigh]",
  "[cough]",
  "[clear throat]",
  "[sniff]",
  "[gasp]",
  "[groan]",
  "[shush]",
];

const DEFAULT_TEXT =
  "Hi there! [chuckle] I'm Athyor. Type anything and I'll say it out loud.";

const Studio = () => {
  const [text, setText] = useState(DEFAULT_TEXT);
  const [temperature, setTemperature] = useState(0.8);
  const [refName, setRefName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const playerRef = useRef<HTMLAudioElement>(null);

  const insertTag = (tag: string) => {
    const el = textareaRef.current;
    if (!el) return;
    const s = el.selectionStart;
    const e = el.selectionEnd;
    const v = el.value;
    const pre = s === 0 || v[s - 1] === " " ? "" : " ";
    const suf = e < v.length && v[e] === " " ? "" : " ";
    const next = v.slice(0, s) + pre + tag + suf + v.slice(e);
    setText(next);
    requestAnimationFrame(() => {
      el.focus();
      el.selectionStart = el.selectionEnd = s + pre.length + tag.length + suf.length;
    });
  };

  const speak = async () => {
    const t = text.trim();
    if (!t) {
      setError(true);
      setStatus("Enter some text first.");
      return;
    }
    setBusy(true);
    setError(false);
    setStatus(
      t.length > 600
        ? "Generating… long texts are synthesized in chunks, this can take a while."
        : "Generating…"
    );
    try {
      const fd = new FormData();
      fd.append("text", t);
      fd.append("temperature", String(temperature));
      const ref = fileRef.current?.files?.[0];
      if (ref) fd.append("ref_audio", ref);

      const r = await fetch("/api/tts", { method: "POST", body: fd });
      if (!r.ok) {
        let msg = `Generation failed (${r.status})`;
        try {
          const j = await r.json();
          msg = j.detail || j.error || msg;
        } catch {}
        throw new Error(msg);
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      setAudioUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return url;
      });
      setStatus("Done.");
      requestAnimationFrame(() => playerRef.current?.play().catch(() => {}));
    } catch (e) {
      setError(true);
      const msg = e instanceof Error ? e.message : String(e);
      setStatus(
        msg.includes("Failed to fetch") || msg.includes("502")
          ? "The voice engine is offline right now — please try again later."
          : msg
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section id="studio" className="w-full bg-black px-4 py-20 sm:px-6 md:px-10 md:py-28">
      <div className="mx-auto max-w-4xl">
        <p className="mb-3 text-[10px] uppercase tracking-[0.35em] text-primary/50 sm:text-xs">
          Athyor / Studio
        </p>
        <h2 className="mb-10 font-medium leading-[0.9] tracking-[-0.05em] text-primary text-5xl sm:text-6xl md:text-7xl">
          <WordsPullUp text="Give it a voice" />
        </h2>

        <motion.div
          initial={{ y: 24, opacity: 0 }}
          whileInView={{ y: 0, opacity: 1 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="relative overflow-hidden rounded-2xl border border-primary/15 bg-primary/[0.04] p-5 sm:p-8 md:rounded-[2rem] md:p-10"
        >
          <div className="noise-overlay pointer-events-none absolute inset-0 opacity-[0.35] mix-blend-overlay" />

          <div className="relative">
            <label className="mb-2 block text-xs text-primary/60">
              What should Athyor say?
            </label>
            <textarea
              ref={textareaRef}
              value={text}
              maxLength={10000}
              onChange={(e) => setText(e.target.value)}
              className="min-h-[130px] w-full resize-y rounded-xl border border-primary/20 bg-black/60 p-4 text-sm text-primary placeholder:text-primary/30 focus:border-primary/60 focus:outline-none sm:text-base"
              placeholder="Type something worth hearing…"
            />

            <div className="mt-3 flex flex-wrap gap-2">
              {TAGS.map((tag) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => insertTag(tag)}
                  className="rounded-full border border-primary/25 px-3 py-1 text-[11px] text-primary/70 transition-colors hover:border-primary/60 hover:text-primary sm:text-xs"
                >
                  {tag}
                </button>
              ))}
            </div>

            <div className="mt-8 grid gap-6 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-xs text-primary/60">
                  Expressiveness: {temperature.toFixed(2)}
                </label>
                <input
                  type="range"
                  min={0.05}
                  max={2}
                  step={0.05}
                  value={temperature}
                  onChange={(e) => setTemperature(Number(e.target.value))}
                  className="w-full"
                />
              </div>
              <div>
                <label className="mb-2 flex items-center gap-1.5 text-xs text-primary/60">
                  <Mic className="h-3.5 w-3.5" />
                  Reference voice (optional, 5–15s clip)
                </label>
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="w-full truncate rounded-full border border-primary/25 px-4 py-2 text-left text-xs text-primary/70 transition-colors hover:border-primary/60 hover:text-primary"
                >
                  {refName ?? "Choose an audio clip…"}
                </button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="audio/*"
                  className="hidden"
                  onChange={(e) => setRefName(e.target.files?.[0]?.name ?? null)}
                />
              </div>
            </div>

            <button
              type="button"
              onClick={speak}
              disabled={busy}
              className="group mt-8 inline-flex items-center gap-2 rounded-full bg-primary py-1 pl-5 pr-1 text-sm font-medium text-black transition-all hover:gap-3 disabled:cursor-wait disabled:opacity-60 sm:text-base"
            >
              {busy ? "Generating…" : "Speak"}
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-black transition-transform group-hover:scale-110 sm:h-10 sm:w-10">
                {busy ? (
                  <LoaderCircle className="h-4 w-4 animate-spin" style={{ color: "#E1E0CC" }} />
                ) : (
                  <Volume2 className="h-4 w-4" style={{ color: "#E1E0CC" }} />
                )}
              </span>
            </button>

            {audioUrl && (
              <audio ref={playerRef} controls src={audioUrl} className="mt-6 w-full" />
            )}
            <p
              className={`mt-3 min-h-[1.2em] text-xs ${
                error ? "text-red-400" : "text-primary/50"
              }`}
            >
              {status}
            </p>
          </div>
        </motion.div>

        {/* About */}
        <div id="about" className="mt-20 grid gap-6 md:mt-28 md:grid-cols-3">
          {[
            {
              title: "Expressive by default",
              body: "Drop tags like [laugh] or [sigh] anywhere in your text and Athyor performs them, not just reads them.",
            },
            {
              title: "Any voice, ten seconds",
              body: "Upload a short reference clip and Athyor carries on in that voice — no training, no setup.",
            },
            {
              title: "Long-form ready",
              body: "Up to 10,000 characters per request; long texts are synthesized in chunks and streamed back as they're ready.",
            },
          ].map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ y: 24, opacity: 0 }}
              whileInView={{ y: 0, opacity: 1 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.7, delay: i * 0.12, ease: [0.16, 1, 0.3, 1] }}
              className="rounded-2xl border border-primary/15 p-6"
            >
              <h3 className="mb-2 text-base font-medium text-primary">{f.title}</h3>
              <p className="text-sm leading-relaxed text-primary/60">{f.body}</p>
            </motion.div>
          ))}
        </div>

        <footer className="mt-20 flex items-center justify-between border-t border-primary/10 pt-6 text-xs text-primary/40">
          <span>Athyor*</span>
          <a
            href="mailto:sge.ailab@gmail.com"
            className="inline-flex items-center gap-1 transition-colors hover:text-primary"
          >
            Inquiries <ArrowRight className="h-3 w-3" />
          </a>
        </footer>
      </div>
    </section>
  );
};

export { Studio };
