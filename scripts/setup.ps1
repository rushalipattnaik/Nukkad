$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location "$root\backend"
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip --quiet
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt --quiet
Pop-Location

Push-Location "$root\frontend"
npm install --silent
Pop-Location

if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
}

Write-Host "Setup complete. Add your SERPAPI_API_KEY to .env, then run run_backend.ps1 and run_frontend.ps1."
