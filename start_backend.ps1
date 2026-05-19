# Start Backend (dev mode)
# Run from project root

$env:Path = "C:\nodejs;" + $env:Path

Write-Host "=== Draft Document AI Agent - Backend ===" -ForegroundColor Cyan

Set-Location "$PSScriptRoot\backend"

# Create .env if missing
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "[INFO] Created .env from .env.example. Edit it to configure LM Studio model name." -ForegroundColor Yellow
}

# Create virtual environment if missing
if (-not (Test-Path "venv\Scripts\pip.exe")) {
    Write-Host "[INFO] Creating Python virtual environment..." -ForegroundColor Yellow
    python -m venv venv --copies 2>&1 | Out-Null
    if (-not (Test-Path "venv\Scripts\pip.exe")) {
        Write-Host "[ERROR] Failed to create venv. Please run: python -m venv venv" -ForegroundColor Red
        exit 1
    }
}

# Activate venv
. .\venv\Scripts\Activate.ps1

# Install dependencies
Write-Host "[INFO] Installing Python dependencies..." -ForegroundColor Yellow
.\venv\Scripts\pip.exe install -r requirements.txt --quiet

# Create data directories
New-Item -ItemType Directory -Force -Path "data\chroma_db", "data\documents", "data\exports" | Out-Null

# Ingest documents
Write-Host "[INFO] Ingesting documents from Document/ folder..." -ForegroundColor Yellow
python ingest_documents.py

# Start API server
Write-Host "[INFO] Starting FastAPI server on http://localhost:8000" -ForegroundColor Green
Write-Host "[INFO] API docs: http://localhost:8000/docs" -ForegroundColor Green
.\venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000
