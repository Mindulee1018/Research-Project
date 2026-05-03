Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "[setup] Creating Python virtual environment (.venv) if missing..."
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

Write-Host "[setup] Installing backend dependencies..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Write-Host "[setup] Installing training dependencies..."
& .\.venv\Scripts\python.exe -m pip install -r notebooks\requirements.txt

Write-Host "[setup] Installing frontend dependencies..."
npm install --prefix frontend

Write-Host "[setup] Setup complete."
