# Starts the Nukkad FastAPI backend on http://localhost:8000
# Run from the project root:  .\scripts\run_backend.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path "$root\.env")) {
    Write-Error ".env not found at project root. Run .\scripts\setup.ps1 first, then edit .env."
    exit 1
}

Push-Location "$root\backend"
# Copy the root .env so python-dotenv (which looks relative to the backend
# working directory) picks it up. We only copy if the backend doesn't
# already have its own newer one.
Copy-Item "$root\.env" ".\.env" -Force

Write-Host "Starting backend on http://localhost:8000 (docs at /docs) ..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000
Pop-Location
