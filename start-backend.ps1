# Starts the voice agent GPU backend and exposes it to the Vercel site.
#  1. Launches the FastAPI TTS server on port 8000
#  2. Opens a Cloudflare quick tunnel to it
#  3. Points the Vercel deployment at the new tunnel URL and redeploys
# Keep this window open while you want the site to work; Ctrl+C to stop.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$key = Get-Content .backend-key -Raw

# --- 1. API server ---
Write-Host "Starting TTS server on http://127.0.0.1:8000 ..."
$server = Start-Process -PassThru -WindowStyle Minimized powershell -ArgumentList `
    "-NoExit", "-Command",
    "`$env:VOICE_AGENT_KEY='$key'; Set-Location '$PSScriptRoot'; & .\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8000"

$deadline = (Get-Date).AddMinutes(5)
while ($true) {
    try {
        $h = Invoke-RestMethod http://127.0.0.1:8000/health -TimeoutSec 2
        if ($h.model_loaded) { break }
    } catch {}
    if ((Get-Date) -gt $deadline) { throw "Server did not become healthy in 5 minutes" }
    Start-Sleep -Seconds 2
}
Write-Host "Model loaded (device: $((Invoke-RestMethod http://127.0.0.1:8000/health).device))"

# --- 2. Tunnel ---
Write-Host "Opening Cloudflare tunnel..."
$log = Join-Path $env:TEMP "voiceagent-tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue
$tunnel = Start-Process -PassThru -WindowStyle Minimized $cloudflared -ArgumentList `
    "tunnel", "--url", "http://127.0.0.1:8000", "--logfile", $log
$deadline = (Get-Date).AddMinutes(2)
$url = $null
while (-not $url) {
    if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches |
             ForEach-Object { $_.Matches } | Select-Object -First 1
        if ($m) { $url = $m.Value }
    }
    if ((Get-Date) -gt $deadline) { throw "Tunnel URL not found within 2 minutes (see $log)" }
    Start-Sleep -Seconds 2
}
Write-Host "Tunnel up: $url"

# --- 3. Point Vercel at the tunnel and redeploy ---
Write-Host "Updating Vercel env and redeploying..."
vercel env rm BACKEND_URL production --yes 2>$null
vercel env add BACKEND_URL production --value $url --yes
vercel env rm BACKEND_KEY production --yes 2>$null
vercel env add BACKEND_KEY production --value $key.Trim() --yes
vercel --prod --yes

Write-Host ""
Write-Host "============================================================"
Write-Host " Voice agent backend is LIVE through $url"
Write-Host " Your Vercel site now talks to this PC. Keep this window open."
Write-Host " Press Ctrl+C (or close this window) to stop serving."
Write-Host "============================================================"
Wait-Process -Id $tunnel.Id
