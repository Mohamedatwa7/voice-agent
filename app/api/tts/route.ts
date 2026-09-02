// Proxies TTS requests to the GPU backend (Cloudflare tunnel URL in BACKEND_URL),
// keeping the backend key server-side.
export const maxDuration = 300;

export async function POST(req: Request) {
  const backend = process.env.BACKEND_URL;
  if (!backend) {
    return Response.json({ error: "BACKEND_URL is not configured" }, { status: 500 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${backend.replace(/\/$/, "")}/tts`, {
      method: "POST",
      headers: {
        "content-type": req.headers.get("content-type") || "application/octet-stream",
        "x-api-key": process.env.BACKEND_KEY || "",
      },
      body: req.body,
      // required by Node's fetch when sending a streaming body
      // @ts-expect-error -- duplex is not in the TS lib types yet
      duplex: "half",
    });
  } catch (err) {
    const cause = (err as { cause?: { code?: string } })?.cause?.code;
    const msg = cause || (err instanceof Error ? err.message : String(err));
    return Response.json({ error: `Backend unreachable: ${msg}` }, { status: 502 });
  }

  // Stream instead of buffering — long texts produce responses well past
  // the buffered-function limit.
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") || "application/octet-stream",
    },
  });
}
