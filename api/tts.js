// Proxies TTS requests to the GPU backend (Cloudflare tunnel URL in BACKEND_URL),
// keeping the backend key server-side.
export const config = { api: { bodyParser: false }, maxDuration: 300 };

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ error: "Method not allowed" });
    return;
  }
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    res.status(500).json({ error: "BACKEND_URL is not configured" });
    return;
  }

  const chunks = [];
  for await (const c of req) chunks.push(c);
  const body = Buffer.concat(chunks);

  let upstream;
  try {
    upstream = await fetch(`${backend.replace(/\/$/, "")}/tts`, {
      method: "POST",
      headers: {
        "content-type": req.headers["content-type"] || "application/octet-stream",
        "x-api-key": process.env.BACKEND_KEY || "",
      },
      body,
    });
  } catch (err) {
    res.status(502).json({ error: `Backend unreachable: ${err?.cause?.code || err?.message || err}` });
    return;
  }

  res.status(upstream.status);
  res.setHeader(
    "content-type",
    upstream.headers.get("content-type") || "application/octet-stream"
  );
  // stream instead of buffering — long texts produce responses well past
  // the 4.5MB buffered-function limit
  for await (const chunk of upstream.body) {
    res.write(Buffer.from(chunk));
  }
  res.end();
}
