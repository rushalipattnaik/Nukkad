# Runs the full backend test suite. Uses mocked SerpApi/Gemini responses
# only - this NEVER spends a real SerpApi credit.
# Run from the project root:  .\scripts\run_tests.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location "$root\backend"
& ".\.venv\Scripts\python.exe" -m pytest -v
Pop-Location
