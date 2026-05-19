# Start Frontend (dev mode)
# Run from project root

$env:Path = "C:\nodejs;" + $env:Path

Write-Host "=== Draft Document AI Agent - Frontend ===" -ForegroundColor Cyan

Set-Location "$PSScriptRoot\frontend"

Write-Host "[INFO] Installing Node.js dependencies..." -ForegroundColor Yellow
npm install

Write-Host "[INFO] Starting Next.js dev server on http://localhost:3000" -ForegroundColor Green
npm run dev
