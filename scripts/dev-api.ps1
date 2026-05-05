# Start FastAPI from repo root with PYTHONPATH so `tenant_alert` (under src/) imports.
# Usage (from anywhere):  pwsh -File D:\Tenant-Alert\scripts\dev-api.ps1
# Or:  cd D:\Tenant-Alert\scripts; .\dev-api.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH = "${root};${root}\src"
Set-Location $root
$port = if ($env:API_PORT) { $env:API_PORT } else { "8000" }
Write-Host "PYTHONPATH=$($env:PYTHONPATH)"
Write-Host "Listening http://127.0.0.1:${port}/  (GET / returns Tenant Alert API JSON)"
python -m uvicorn api.app.main:app --reload --host 127.0.0.1 --port $port
