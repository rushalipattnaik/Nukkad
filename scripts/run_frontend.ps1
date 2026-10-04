# Starts the Nukkad frontend on http://localhost:5173
# Run from the project root, in a SEPARATE terminal from run_backend.ps1:
#   .\scripts\run_frontend.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location "$root\frontend"
Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Cyan
npm run dev
Pop-Location
