# One-time setup for the Chatterbox voice agent.
# Creates a virtual environment and installs chatterbox-tts from the cloned repo.
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

if (-not (Test-Path .\chatterbox)) {
    Write-Host "Cloning chatterbox..."
    git clone https://github.com/resemble-ai/chatterbox.git
}

if (-not (Test-Path .venv)) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .\chatterbox

# Replace CPU-only torch with CUDA build.
# RTX 5090 (Blackwell, sm_120) needs cu128, which starts at torch 2.7.
& .\.venv\Scripts\python.exe -m pip install torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128 --force-reinstall

Write-Host ""
Write-Host "Setup complete. Start the UI with:  .\run.ps1"
