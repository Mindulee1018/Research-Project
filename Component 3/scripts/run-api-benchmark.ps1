Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [int]$Requests = 500,
    [int]$Workers = 16,
    [double]$TimeoutSec = 20,
    [string]$OutputJson = "evaluation/benchmarks/latest_api_benchmark.json"
)

if (Test-Path ".venv\Scripts\python.exe") {
    $py = ".\.venv\Scripts\python.exe"
} else {
    $py = "python"
}

Write-Host "[api-benchmark] Running benchmark..."
& $py "scripts/benchmark_api.py" `
    --base-url $BaseUrl `
    --requests $Requests `
    --workers $Workers `
    --timeout-sec $TimeoutSec `
    --output-json $OutputJson

Write-Host "[api-benchmark] Completed."
